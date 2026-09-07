# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end state-handling tests for ovos-skill-ggwave.

Complements ``test_intents_en_us.py`` (intent routing) by covering the
idempotent "already enabled/disabled" branches and the ``ggwave.enabled`` /
``ggwave.disabled`` bus-event handlers that the audio transformer plugin drives
-- including the 15-minute auto-disable timeout.

Assertions are subset checks over the captured message stream plus direct
inspection of the skill's state, so they stay robust against ordered-sequence
drift across ovos-core / ovoscope releases.

Run:
    uv run pytest test/end2end/ -v
"""

import time
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft, CaptureSession, PADATIOUS_PIPELINE

from ovos_skill_ggwave import GGWaveSkill

SKILL_ID = "ovos-skill-ggwave.openvoiceos"
# The legacy scheduler names a one-shot event "<skill_id>:<name>"; a
# SCHEDULER-1-capable scheduler names the topic it fires "<skill_id>.<name>"
# instead. Accept either so the assertion holds across ovos-workshop releases.
TIMEOUT_EVENT_CANDIDATES = {f"{SKILL_ID}:ggwave.timeout", f"{SKILL_ID}.ggwave.timeout"}


def _candidates(intent_label: str) -> set:
    """See test_intents_en_us.py's _candidates docstring: different
    padatious/padacioso plugin versions register the matched-intent bus
    event with or without the ``.intent`` filename extension kept."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{SKILL_ID}:{intent_label}", f"{SKILL_ID}:{base}"}


ENABLE_INTENT = _candidates("enable_ggwave.intent")
DISABLE_INTENT = _candidates("disable_ggwave.intent")


def _assert_any_in(candidates, types):
    assert any(t in candidates for t in types), (
        f"expected one of {sorted(candidates)!r} in {types!r}"
    )


def _session(session_id: str) -> Session:
    session = Session(session_id)
    session.pipeline = PADATIOUS_PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": "en-US"},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class _StateTestCase(unittest.TestCase):
    def setUp(self):
        self.minicroft = get_minicroft(
            skill_ids=[], extra_skills={SKILL_ID: GGWaveSkill},
            enable_event_scheduler=True,
        )

    def tearDown(self):
        self.minicroft.stop()

    @property
    def skill(self):
        return self.minicroft.plugin_skills[SKILL_ID].instance

    def _wait_for_scheduler_requests(self, timeout=10):
        # OVOSSkill.schedule_event()/cancel_scheduled_event() hand the
        # request to a background sender thread and return immediately
        # (ovos_workshop.skills.ovos.OVOSSkill._send_to_scheduler). Wait for
        # that queue to drain, but with a deadline: the workshop's own
        # _scheduler_requests_sent() is an unbounded Queue.join(), and a
        # scheduler request that never returns must fail this test, not hang
        # the CI job.
        requests = self.skill._scheduler_requests
        deadline = time.monotonic() + timeout
        while requests.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(
            requests.unfinished_tasks, 0,
            f"scheduler requests still unsent after {timeout}s",
        )

    def _scheduled_event_names(self):
        self._wait_for_scheduler_requests()
        return [name for name, _ in self.skill.event_scheduler.events.events]

    def _capture(self, utterance: str, session_id: str):
        capture = CaptureSession(self.minicroft)
        capture.capture(_utterance(utterance, _session(session_id)), timeout=30)
        return capture.finish()


class TestAlreadyEnabled(_StateTestCase):
    """Enabling when already enabled is idempotent and emits no enable event."""

    def test_enable_when_already_enabled_emits_no_enable(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self.assertTrue(self.skill.enabled)

        messages = self._capture("enable ggwave", "e2e-already-enable")
        types = [m.msg_type for m in messages]

        _assert_any_in(ENABLE_INTENT, types)
        # idempotent: intent matched but no enable side-effect
        self.assertNotIn("ovos.ggwave.enable", types)


class TestAlreadyDisabled(_StateTestCase):
    """Disabling when already disabled is idempotent and emits no disable event."""

    def test_disable_when_already_disabled_emits_no_disable(self):
        self.assertFalse(self.skill.enabled)

        messages = self._capture("disable ggwave", "e2e-already-disable")
        types = [m.msg_type for m in messages]

        _assert_any_in(DISABLE_INTENT, types)
        self.assertNotIn("ovos.ggwave.disable", types)


class TestBusEventHandlers(_StateTestCase):
    """The ggwave.enabled / ggwave.disabled handlers the plugin emits."""

    def test_enabled_event_sets_state_and_schedules_timeout(self):
        self.assertFalse(self.skill.enabled)

        self.minicroft.bus.emit(Message("ggwave.enabled"))

        self.assertTrue(self.skill.enabled)
        _assert_any_in(TIMEOUT_EVENT_CANDIDATES, self._scheduled_event_names())

    def test_disabled_event_clears_state(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self.assertTrue(self.skill.enabled)

        self.minicroft.bus.emit(Message("ggwave.disabled"))
        self.assertFalse(self.skill.enabled)

    def test_disable_intent_routes_while_timeout_pending(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        _assert_any_in(TIMEOUT_EVENT_CANDIDATES, self._scheduled_event_names())

        messages = self._capture("disable ggwave", "e2e-cancel-timeout")
        types = [m.msg_type for m in messages]

        _assert_any_in(DISABLE_INTENT, types)

    def test_disable_intent_cancels_timeout(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        _assert_any_in(TIMEOUT_EVENT_CANDIDATES, self._scheduled_event_names())

        messages = self._capture("disable ggwave", "e2e-cancel-timeout")
        types = [m.msg_type for m in messages]

        _assert_any_in(DISABLE_INTENT, types)
        self.assertIn("ovos.ggwave.disable", types)
        self.assertFalse(TIMEOUT_EVENT_CANDIDATES & set(self._scheduled_event_names()))

    def test_timeout_actually_fires_and_disables(self):
        """The scheduled ggwave.timeout event must really reach
        handle_ggwave_off, not just appear in the scheduler's event list."""
        from unittest.mock import patch

        # Shorten the 15-minute timeout to 1s through the skill's own
        # constant. The skill schedules a number of seconds, so the event is
        # due 1s from now whatever the box's timezone is (a UTC runner with
        # the default America/Chicago configuration included).
        with patch("ovos_skill_ggwave.TIMEOUT_SECONDS", 1):
            self.minicroft.bus.emit(Message("ggwave.enabled"))

        self.assertTrue(self.skill.enabled)

        # A generous bound: the scheduler backend ticks on its own interval
        # and a loaded CI runner can be slow to service it, but 20s is still
        # a tiny fraction of the real 15-minute timeout under test.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and self.skill.enabled:
            time.sleep(0.1)

        self.assertFalse(
            self.skill.enabled,
            "ggwave.timeout did not fire handle_ggwave_off within 20s",
        )


if __name__ == "__main__":
    unittest.main()

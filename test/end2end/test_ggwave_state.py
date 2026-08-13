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

import unittest

import pytest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft, CaptureSession, PADATIOUS_PIPELINE

from ovos_skill_ggwave import GGWaveSkill

SKILL_ID = "ovos-skill-ggwave.openvoiceos"
TIMEOUT_EVENT = f"{SKILL_ID}:ggwave.timeout"


def _candidates(intent_label: str) -> set:
    """See test_intents_en_us.py's _candidates docstring: different
    padatious/padacioso plugin versions register the matched-intent bus
    event with or without the ``.intent`` filename extension kept."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{SKILL_ID}:{intent_label}", f"{SKILL_ID}:{base}"}


ENABLE_INTENT = _candidates("enable_ggwave.intent")
DISABLE_INTENT = _candidates("disable_ggwave.intent")

# KNOWN GAP -- see the matching constant/comment in test_intents_en_us.py.
# On this alpha stack (ovos-workshop 8.3.0a1, ovos-padatious 2.0.1a2,
# ovoscope 0.22.1a1) the handler body bound via @intent_handler("*.intent")
# never runs: OVOSSkill.register_intent_file() binds the bus listener to
# the ".intent"-suffixed event name, but the intent service emits the
# matched-intent message under the stripped name. NOTE: this also means
# TestAlreadyEnabled/TestAlreadyDisabled's "no side-effect emitted" checks
# below are vacuously true under this bug (the handler body -- and thus any
# side effect -- never runs at all, regardless of the already-enabled/
# disabled branch) -- kept as-is since they still correctly describe the
# intended contract and will start actually exercising it once the
# upstream naming mismatch is fixed.
_HANDLER_BINDING_XFAIL = "known gap: handler binding uses '.intent'-suffixed event name but the intent service emits the stripped name on this alpha stack (ovos-workshop 8.3.0a1 / ovos-padatious 2.0.1a2) -- handler body never runs. Intent *routing* itself is correct."


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
            skill_ids=[], extra_skills={SKILL_ID: GGWaveSkill}
        )

    def tearDown(self):
        self.minicroft.stop()

    @property
    def skill(self):
        return self.minicroft.plugin_skills[SKILL_ID].instance

    def _scheduled_event_names(self):
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
        self.assertIn(TIMEOUT_EVENT, self._scheduled_event_names())

    def test_disabled_event_clears_state(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self.assertTrue(self.skill.enabled)

        self.minicroft.bus.emit(Message("ggwave.disabled"))
        self.assertFalse(self.skill.enabled)

    def test_disable_intent_routes_while_timeout_pending(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self.assertIn(TIMEOUT_EVENT, self._scheduled_event_names())

        messages = self._capture("disable ggwave", "e2e-cancel-timeout")
        types = [m.msg_type for m in messages]

        _assert_any_in(DISABLE_INTENT, types)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_disable_intent_cancels_timeout(self):
        # KNOWN GAP: see _HANDLER_BINDING_XFAIL. handle_disable_ggwave's body
        # (which emits ovos.ggwave.disable and cancels the scheduled
        # timeout) never runs on this alpha stack, because the intent
        # service emits the matched-intent message under the stripped
        # "<skill_id>:disable_ggwave" name while OVOSSkill.register_intent_file
        # bound the handler's bus listener to the ".intent"-suffixed name.
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self.assertIn(TIMEOUT_EVENT, self._scheduled_event_names())

        messages = self._capture("disable ggwave", "e2e-cancel-timeout")
        types = [m.msg_type for m in messages]

        _assert_any_in(DISABLE_INTENT, types)
        self.assertIn("ovos.ggwave.disable", types)
        self.assertNotIn(TIMEOUT_EVENT, self._scheduled_event_names())


if __name__ == "__main__":
    unittest.main()

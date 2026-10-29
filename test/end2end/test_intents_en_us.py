# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end intent-routing tests for ovos-skill-ggwave (en-US).

These assert *per-utterance* that the pipeline routes an utterance to the
expected intent handler and that the skill emits its side-effect bus event.
They deliberately use subset assertions over the captured message stream rather
than a strict full-sequence match: the exact ordered sequence drifts across
ovos-core / ovoscope releases (e.g. an extra ``ovos.intent.matched`` message,
or ``speak`` vs ``ovos.utterance.speak``), which is orthogonal to what this
skill is responsible for.

Run:
    uv run pytest test/end2end/ -v
"""

import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

from ovos_skill_ggwave import GGWaveSkill

SKILL_ID = "ovos-skill-ggwave.openvoiceos"


ENABLE_INTENT = f"{SKILL_ID}:enable_ggwave"
DISABLE_INTENT = f"{SKILL_ID}:disable_ggwave"


def _session() -> Session:
    session = Session("e2e-intents")
    session.lang = "en-US"
    session.pipeline = PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": "en-US"},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class _RoutingTestCase(unittest.TestCase):
    """Base class wiring a MiniCroft with the ggwave skill injected."""

    def setUp(self):
        self.minicroft = get_prototype_minicroft(
            [], lang="en-US", extra_skills={SKILL_ID: GGWaveSkill}
        )

    def tearDown(self):
        self.minicroft.stop()

    def _capture(self, utterance: str, intent: str):
        """Speak ``utterance`` and return the captured messages."""
        session = _session()
        capture = CaptureSession(self.minicroft)
        capture.capture(_utterance(utterance, session), timeout=30)
        messages = capture.finish()
        TALLY.assert_routed(utterance, intent, [m.msg_type for m in messages])
        return messages

    def assertEmitted(self, messages, msg_type):
        types = [m.msg_type for m in messages]
        self.assertIn(
            msg_type, types,
            f"expected {msg_type!r} to be emitted, got {types}",
        )

    def assertNotEmitted(self, messages, msg_type):
        types = [m.msg_type for m in messages]
        self.assertNotIn(
            msg_type, types,
            f"did not expect {msg_type!r} to be emitted, got {types}",
        )


class TestEnableRouting(_RoutingTestCase):
    """Utterances that must route to enable_ggwave and emit the enable event."""

    def test_enable_ggwave(self):
        self._capture("enable ggwave", ENABLE_INTENT)

    def test_enable_ggwave_side_effect(self):
        messages = self._capture("enable ggwave", ENABLE_INTENT)
        self.assertEmitted(messages, "ovos.ggwave.enable")

    def test_turn_on_audio_codes(self):
        self._capture("turn on audio codes", ENABLE_INTENT)

    def test_turn_on_audio_codes_side_effect(self):
        messages = self._capture("turn on audio codes", ENABLE_INTENT)
        self.assertEmitted(messages, "ovos.ggwave.enable")

    def test_activate_data_over_sound(self):
        self._capture("activate data over sound", ENABLE_INTENT)

    def test_activate_data_over_sound_side_effect(self):
        messages = self._capture("activate data over sound", ENABLE_INTENT)
        self.assertEmitted(messages, "ovos.ggwave.enable")


class TestDisableRouting(_RoutingTestCase):
    """Utterances that must route to disable_ggwave."""

    def test_disable_ggwave(self):
        # pre-enable so the disable branch emits its bus event
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self._capture("disable ggwave", DISABLE_INTENT)

    def test_disable_ggwave_side_effect(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("disable ggwave", DISABLE_INTENT)
        self.assertEmitted(messages, "ovos.ggwave.disable")

    def test_turn_off_audio_data(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        self._capture("turn off audio data", DISABLE_INTENT)

    def test_turn_off_audio_data_side_effect(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("turn off audio data", DISABLE_INTENT)
        self.assertEmitted(messages, "ovos.ggwave.disable")


if __name__ == "__main__":
    unittest.main()

# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end intent-routing tests for ovos-skill-ggwave (en-US).

These assert *per-utterance* that the Padatious pipeline routes an utterance to
the expected intent handler and that the skill emits its side-effect bus event.
They deliberately use subset assertions over the captured message stream rather
than a strict full-sequence match: the exact ordered sequence drifts across
ovos-core / ovoscope releases (e.g. an extra ``ovos.intent.matched`` message,
or ``speak`` vs ``ovos.utterance.speak``), which is orthogonal to what this
skill is responsible for.

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


def _candidates(intent_label: str) -> set:
    """Different padatious/padacioso plugin versions register the
    matched-intent bus event under different normalizations of the
    ``.intent`` filename basename -- observed variants include the bare
    basename with no extension (current OVOS-INTENT-2 naming, see
    ovos-skill-parrot#119) and the basename with the extension kept (older
    naming). Candidates cover both so the suite isn't pinned to whichever
    naming happens to be installed."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{SKILL_ID}:{intent_label}", f"{SKILL_ID}:{base}"}


ENABLE_INTENT = _candidates("enable_ggwave.intent")
DISABLE_INTENT = _candidates("disable_ggwave.intent")

# KNOWN GAP (finding, not a skill defect): on the pinned alpha stack used by
# this suite (ovos-workshop==8.3.0a1, ovos-padatious==2.0.1a2,
# ovoscope==0.22.1a1), OVOSSkill.register_intent_file() registers the
# handler's bus listener under "<skill_id>:<name>.intent" (add_event() call
# in ovos_workshop/skills/ovos.py), but the intent service actually emits
# the matched-intent message under the *stripped* "<skill_id>:<name>"
# (verified directly against the live bus stream: only
# ["recognizer_loop:utterance", "<skill_id>.activate",
# "<skill_id>:enable_ggwave"] are ever observed -- no
# "mycroft.skill.handler.start" and no "ovos.ggwave.enable" follow). The
# intent-routing message itself IS correct (see assertIntentMatched above,
# which passes) -- only the *handler-body side effect* never fires, because
# the handler is never invoked at all. This is the same OVOS-INTENT-2
# padatious-naming migration class of bug documented in
# ovos-skill-volume's golden suite (ovos-skill-parrot#119), one layer
# deeper: there the *match* message name drifted; here the *handler
# binding* itself drifted out of sync with it. Not something to patch in
# this skill repo -- flagging for the ovos-workshop/ovos-padatious pairing.
_HANDLER_BINDING_XFAIL = "known gap: handler binding uses '.intent'-suffixed event name but the intent service emits the stripped name on this alpha stack (ovos-workshop 8.3.0a1 / ovos-padatious 2.0.1a2) -- handler body never runs, so its ovos.ggwave.(en|dis)able side effect is never observed. Intent *routing* itself is correct (see assertIntentMatched)."


def _session() -> Session:
    session = Session("e2e-intents")
    session.pipeline = PADATIOUS_PIPELINE
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
        self.minicroft = get_minicroft(
            skill_ids=[], extra_skills={SKILL_ID: GGWaveSkill}
        )

    def tearDown(self):
        self.minicroft.stop()

    def _capture(self, utterance: str):
        session = _session()
        capture = CaptureSession(self.minicroft)
        capture.capture(_utterance(utterance, session), timeout=30)
        return capture.finish()

    def assertIntentMatched(self, messages, intent_candidates):
        types = [m.msg_type for m in messages]
        self.assertTrue(
            any(t in intent_candidates for t in types),
            f"expected one of {sorted(intent_candidates)!r} to be matched, got {types}",
        )

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
        messages = self._capture("enable ggwave")
        self.assertIntentMatched(messages, ENABLE_INTENT)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_enable_ggwave_side_effect(self):
        messages = self._capture("enable ggwave")
        self.assertEmitted(messages, "ovos.ggwave.enable")

    def test_turn_on_audio_codes(self):
        messages = self._capture("turn on audio codes")
        self.assertIntentMatched(messages, ENABLE_INTENT)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_turn_on_audio_codes_side_effect(self):
        messages = self._capture("turn on audio codes")
        self.assertEmitted(messages, "ovos.ggwave.enable")

    def test_activate_data_over_sound(self):
        messages = self._capture("activate data over sound")
        self.assertIntentMatched(messages, ENABLE_INTENT)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_activate_data_over_sound_side_effect(self):
        messages = self._capture("activate data over sound")
        self.assertEmitted(messages, "ovos.ggwave.enable")


class TestDisableRouting(_RoutingTestCase):
    """Utterances that must route to disable_ggwave."""

    def test_disable_ggwave(self):
        # pre-enable so the disable branch emits its bus event
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("disable ggwave")
        self.assertIntentMatched(messages, DISABLE_INTENT)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_disable_ggwave_side_effect(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("disable ggwave")
        self.assertEmitted(messages, "ovos.ggwave.disable")

    def test_turn_off_audio_data(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("turn off audio data")
        self.assertIntentMatched(messages, DISABLE_INTENT)

    @pytest.mark.xfail(strict=True, reason=_HANDLER_BINDING_XFAIL)
    def test_turn_off_audio_data_side_effect(self):
        self.minicroft.bus.emit(Message("ggwave.enabled"))
        messages = self._capture("turn off audio data")
        self.assertEmitted(messages, "ovos.ggwave.disable")


if __name__ == "__main__":
    unittest.main()

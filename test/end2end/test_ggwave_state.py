# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end tests for ovos-skill-ggwave state handling.

Complements ``test_ggwave.py`` (the happy-path enable/disable intents) by
covering the idempotent "already enabled/disabled" branches and the
``ggwave.enabled`` / ``ggwave.disabled`` bus-event handlers that the audio
transformer plugin drives — including the 15-minute auto-disable timeout.

Run:
    uv run pytest test/end2end/ -v
"""

import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import End2EndTest, PADATIOUS_PIPELINE, get_minicroft

SKILL_ID = "ovos-skill-ggwave.openvoiceos"
TIMEOUT_EVENT = f"{SKILL_ID}:ggwave.timeout"


def _padatious_session(session_id: str) -> Session:
    session = Session(session_id)
    session.pipeline = PADATIOUS_PIPELINE
    return session


def _utterance_message(utterance: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utterance], "lang": "en-US"},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


def _scheduled_event_names(minicroft) -> list:
    """Return the names of events scheduled by the running skill."""
    inst = minicroft.plugin_skills[SKILL_ID].instance
    return [name for name, _ in inst.event_scheduler.events.events]


class TestAlreadyEnabled(unittest.TestCase):
    """Enabling when already enabled is idempotent and emits no enable."""

    def test_enable_when_already_enabled_speaks_already_dialog(self):
        minicroft = get_minicroft([SKILL_ID])
        try:
            # pre-enable via the plugin's bus event
            minicroft.bus.emit(Message("ggwave.enabled"))

            session = _padatious_session("e2e-already-enable")
            utterance = _utterance_message("enable ggwave", session)

            test = End2EndTest(
                minicroft=minicroft,
                skill_ids=[SKILL_ID],
                source_message=utterance,
                expected_messages=[
                    utterance,
                    Message(f"{SKILL_ID}.activate", data={},
                            context={"skill_id": SKILL_ID}),
                    Message(f"{SKILL_ID}:enable_ggwave.intent",
                            data={"utterance": "enable ggwave", "lang": "en-US"},
                            context={"skill_id": SKILL_ID}),
                    Message("mycroft.skill.handler.start",
                            data={"name": "GGWaveSkill.handle_enable_ggwave"},
                            context={"skill_id": SKILL_ID}),
                    # idempotent: speaks "already enabled", NO ovos.ggwave.enable
                    Message("speak",
                            data={"utterance": "audio QR codes already enabled",
                                  "lang": "en-US"},
                            context={"skill_id": SKILL_ID}),
                    Message("mycroft.skill.handler.complete",
                            data={"name": "GGWaveSkill.handle_enable_ggwave"},
                            context={"skill_id": SKILL_ID}),
                    Message("ovos.utterance.handled", data={},
                            context={"skill_id": SKILL_ID}),
                ],
                test_msg_context=False,
            )
            test.execute(timeout=30)
        finally:
            minicroft.stop()


class TestAlreadyDisabled(unittest.TestCase):
    """Disabling when already disabled is idempotent and emits no disable."""

    def test_disable_when_already_disabled_speaks_already_dialog(self):
        session = _padatious_session("e2e-already-disable")
        utterance = _utterance_message("disable ggwave", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(f"{SKILL_ID}.activate", data={},
                        context={"skill_id": SKILL_ID}),
                Message(f"{SKILL_ID}:disable_ggwave.intent",
                        data={"utterance": "disable ggwave", "lang": "en-US"},
                        context={"skill_id": SKILL_ID}),
                Message("mycroft.skill.handler.start",
                        data={"name": "GGWaveSkill.handle_disable_ggwave"},
                        context={"skill_id": SKILL_ID}),
                # idempotent: speaks "already disabled", NO ovos.ggwave.disable
                Message("speak",
                        data={"utterance": "audio QR codes already disabled",
                              "lang": "en-US"},
                        context={"skill_id": SKILL_ID}),
                Message("mycroft.skill.handler.complete",
                        data={"name": "GGWaveSkill.handle_disable_ggwave"},
                        context={"skill_id": SKILL_ID}),
                Message("ovos.utterance.handled", data={},
                        context={"skill_id": SKILL_ID}),
            ],
            test_msg_context=False,
        )
        test.execute(timeout=30)


class TestBusEventHandlers(unittest.TestCase):
    """The ggwave.enabled / ggwave.disabled handlers the plugin emits."""

    def test_enabled_event_sets_state_and_schedules_timeout(self):
        minicroft = get_minicroft([SKILL_ID])
        try:
            inst = minicroft.plugin_skills[SKILL_ID].instance
            self.assertFalse(inst.enabled)

            minicroft.bus.emit(Message("ggwave.enabled"))

            self.assertTrue(inst.enabled)
            self.assertIn(TIMEOUT_EVENT, _scheduled_event_names(minicroft))
        finally:
            minicroft.stop()

    def test_disabled_event_clears_state(self):
        minicroft = get_minicroft([SKILL_ID])
        try:
            inst = minicroft.plugin_skills[SKILL_ID].instance

            minicroft.bus.emit(Message("ggwave.enabled"))
            self.assertTrue(inst.enabled)

            minicroft.bus.emit(Message("ggwave.disabled"))
            self.assertFalse(inst.enabled)
        finally:
            minicroft.stop()

    def test_disable_intent_cancels_timeout(self):
        """The disable intent removes the pending auto-disable timeout."""
        minicroft = get_minicroft([SKILL_ID])
        try:
            minicroft.bus.emit(Message("ggwave.enabled"))
            self.assertIn(TIMEOUT_EVENT, _scheduled_event_names(minicroft))

            session = _padatious_session("e2e-cancel-timeout")
            utterance = _utterance_message("disable ggwave", session)
            End2EndTest(
                minicroft=minicroft,
                skill_ids=[SKILL_ID],
                source_message=utterance,
                expected_messages=[
                    utterance,
                    Message(f"{SKILL_ID}.activate", data={},
                            context={"skill_id": SKILL_ID}),
                    Message(f"{SKILL_ID}:disable_ggwave.intent",
                            data={"utterance": "disable ggwave", "lang": "en-US"},
                            context={"skill_id": SKILL_ID}),
                    Message("mycroft.skill.handler.start",
                            data={"name": "GGWaveSkill.handle_disable_ggwave"},
                            context={"skill_id": SKILL_ID}),
                    Message("ovos.ggwave.disable", data={},
                            context={"skill_id": SKILL_ID}),
                    Message("mycroft.scheduler.remove_event",
                            data={"event": TIMEOUT_EVENT},
                            context={"skill_id": SKILL_ID}),
                    Message("speak",
                            data={"utterance": "disabling audio QR codes",
                                  "lang": "en-US"},
                            context={"skill_id": SKILL_ID}),
                    Message("mycroft.skill.handler.complete",
                            data={"name": "GGWaveSkill.handle_disable_ggwave"},
                            context={"skill_id": SKILL_ID}),
                    Message("ovos.utterance.handled", data={},
                            context={"skill_id": SKILL_ID}),
                ],
                test_msg_context=False,
            ).execute(timeout=30)

            self.assertNotIn(TIMEOUT_EVENT, _scheduled_event_names(minicroft))
        finally:
            minicroft.stop()


if __name__ == "__main__":
    unittest.main()

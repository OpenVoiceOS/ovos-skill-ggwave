# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end tests for ovos-skill-ggwave using ovoscope.

These tests verify the full intent-matching and message-sequence behaviour:
  - utterances are matched by the Padatious pipeline
  - correct bus messages are emitted in the right order
  - dialog responses match expected strings

Run:
    uv run pytest test/end2end/ -v
"""

import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import End2EndTest, PADATIOUS_PIPELINE

SKILL_ID = "ovos-skill-ggwave.openvoiceos"


def _padatious_session(session_id: str) -> Session:
    """Return a Session restricted to Padatious."""
    session = Session(session_id)
    session.pipeline = PADATIOUS_PIPELINE
    return session


def _utterance_message(utterance: str, session: Session) -> Message:
    """Build a recognizer_loop:utterance Message."""
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utterance], "lang": "en-US"},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class TestEnableGGWave(unittest.TestCase):
    """End-to-end tests for the 'enable ggwave' intent."""

    def test_enable_ggwave_utterance_matched_and_emits_enable(self) -> None:
        """'enable ggwave' matches enable_ggwave.intent, emits ovos.ggwave.enable and speaks."""
        session = _padatious_session("e2e-enable-1")
        utterance = _utterance_message("enable ggwave", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:enable_ggwave.intent",
                    data={"utterance": "enable ggwave", "lang": "en-US"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "mycroft.skill.handler.start",
                    data={"name": "GGWaveSkill.handle_enable_ggwave"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.ggwave.enable",
                    data={},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "speak",
                    data={
                        "utterance": "enabling audio QR codes for 15 minutes",
                        "lang": "en-US",
                    },
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "mycroft.skill.handler.complete",
                    data={"name": "GGWaveSkill.handle_enable_ggwave"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled",
                    data={},
                    context={"skill_id": SKILL_ID},
                ),
            ],
            test_msg_context=False,
        )
        test.execute(timeout=30)


class TestDisableGGWave(unittest.TestCase):
    """End-to-end tests for the 'disable ggwave' intent."""

    def test_disable_ggwave_utterance_matched_and_emits_disable(self) -> None:
        """'disable ggwave' matches disable_ggwave.intent, emits ovos.ggwave.disable and speaks."""
        from ovoscope import get_minicroft

        minicroft = get_minicroft([SKILL_ID])
        try:
            minicroft.bus.emit(Message("ggwave.enabled"))

            session = _padatious_session("e2e-disable-1")
            utterance = _utterance_message("disable ggwave", session)

            test = End2EndTest(
                minicroft=minicroft,
                skill_ids=[SKILL_ID],
                source_message=utterance,
                expected_messages=[
                    utterance,
                    Message(
                        f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                    ),
                    Message(
                        f"{SKILL_ID}:disable_ggwave.intent",
                        data={"utterance": "disable ggwave", "lang": "en-US"},
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "mycroft.skill.handler.start",
                        data={"name": "GGWaveSkill.handle_disable_ggwave"},
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "ovos.ggwave.disable",
                        data={},
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "mycroft.scheduler.remove_event",
                        data={"event": f"{SKILL_ID}:ggwave.timeout"},
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "speak",
                        data={
                            "utterance": "disabling audio QR codes",
                            "lang": "en-US",
                        },
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "mycroft.skill.handler.complete",
                        data={"name": "GGWaveSkill.handle_disable_ggwave"},
                        context={"skill_id": SKILL_ID},
                    ),
                    Message(
                        "ovos.utterance.handled",
                        data={},
                        context={"skill_id": SKILL_ID},
                    ),
                ],
                test_msg_context=False,
            )
            test.execute(timeout=30)
        finally:
            minicroft.stop()


if __name__ == "__main__":
    unittest.main()

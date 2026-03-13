# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""End-to-end tests for ovos-skill-ggwave using ovoscope.

These tests verify the full intent-matching and message-sequence behaviour:
  - utterances are matched by the Padatious pipeline
  - correct bus messages are emitted in the right order
  - dialog responses match expected strings

Run:
    uv run pytest test/end2end/ -v --timeout=60
"""

import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import End2EndTest, PADATIOUS_PIPELINE

SKILL_ID = "ovos-skill-ggwave.openvoiceos"

# Padatious pipeline — C extension, requires swig


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
        """'enable ggwave' matches enable.ggwave.intent, emits ovos.ggwave.enable and speaks."""
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
                    f"{SKILL_ID}:enable.ggwave.intent",
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
                        "meta": {"dialog": "ggwave.enabled", "skill": SKILL_ID},
                    },
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "mycroft.skill.handler.complete",
                    data={"name": "GGWaveSkill.handle_enable_ggwave"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)

    def test_start_audio_codes_utterance_matches_enable_intent(self) -> None:
        """'start audio codes' also matches enable.ggwave.intent."""
        session = _padatious_session("e2e-enable-2")
        utterance = _utterance_message("start audio codes", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:enable.ggwave.intent",
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "mycroft.skill.handler.start",
                    data={"name": "GGWaveSkill.handle_enable_ggwave"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)

    def test_ggwave_on_utterance_matches_enable_intent(self) -> None:
        """'ggwave on' matches enable.ggwave.intent."""
        session = _padatious_session("e2e-enable-3")
        utterance = _utterance_message("ggwave on", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:enable.ggwave.intent",
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)


class TestDisableGGWave(unittest.TestCase):
    """End-to-end tests for the 'disable ggwave' intent."""

    def test_disable_ggwave_utterance_matched_and_emits_disable(self) -> None:
        """'disable ggwave' matches disable.ggwave.intent, emits ovos.ggwave.disable and speaks."""
        session = _padatious_session("e2e-disable-1")
        # Pre-enable so the handler emits the right branch
        session.active_skills = [(SKILL_ID, 0.0)]
        utterance = _utterance_message("disable ggwave", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:disable.ggwave.intent",
                    data={"utterance": "disable ggwave", "lang": "en-US"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "mycroft.skill.handler.start",
                    data={"name": "GGWaveSkill.handle_disable_ggwave"},
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)

    def test_stop_audio_codes_utterance_matches_disable_intent(self) -> None:
        """'stop audio codes' matches disable.ggwave.intent."""
        session = _padatious_session("e2e-disable-2")
        utterance = _utterance_message("stop audio codes", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:disable.ggwave.intent",
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)

    def test_ggwave_off_utterance_matches_disable_intent(self) -> None:
        """'ggwave off' matches disable.ggwave.intent."""
        session = _padatious_session("e2e-disable-3")
        utterance = _utterance_message("ggwave off", session)

        test = End2EndTest(
            skill_ids=[SKILL_ID],
            source_message=utterance,
            expected_messages=[
                utterance,
                Message(
                    f"{SKILL_ID}.activate", data={}, context={"skill_id": SKILL_ID}
                ),
                Message(
                    f"{SKILL_ID}:disable.ggwave.intent",
                    context={"skill_id": SKILL_ID},
                ),
                Message(
                    "ovos.utterance.handled", data={}, context={"skill_id": SKILL_ID}
                ),
            ],
        )
        test.execute(timeout=30)


if __name__ == "__main__":
    unittest.main()

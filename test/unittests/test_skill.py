# Copyright 2024 OpenVoiceOS
# Licensed under the Apache License, Version 2.0
"""Unit tests for GGWaveSkill.

Tests cover handler logic in isolation using FakeBus.
For full intent-matching and message-sequence tests, see test/end2end/.
"""

import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from ovos_utils.fakebus import FakeBus
from ovos_bus_client.message import Message


class TestGGWaveSkillHandlers(unittest.TestCase):
    """Unit tests for GGWaveSkill internal handler logic."""

    def setUp(self) -> None:
        """Set up a GGWaveSkill instance backed by a FakeBus."""
        from ovos_skill_ggwave import GGWaveSkill

        self.bus = FakeBus()
        self.skill = GGWaveSkill(bus=self.bus, skill_id="ovos-skill-ggwave.openvoiceos")
        self.skill._startup(self.bus, "ovos-skill-ggwave.openvoiceos")

    def tearDown(self) -> None:
        """Clean up skill resources."""
        self.skill.shutdown()

    # ------------------------------------------------------------------ #
    # initialize                                                           #
    # ------------------------------------------------------------------ #

    def test_initialize_sets_enabled_false(self) -> None:
        """GGWaveSkill.initialize sets self.enabled to False."""
        self.assertFalse(self.skill.enabled)

    def test_initialize_registers_ggwave_enabled_event(self) -> None:
        """GGWaveSkill.initialize registers 'ggwave.enabled' bus event."""
        listeners = self.bus.ee.listeners("ggwave.enabled")
        self.assertTrue(len(listeners) > 0)

    def test_initialize_registers_ggwave_disabled_event(self) -> None:
        """GGWaveSkill.initialize registers 'ggwave.disabled' bus event."""
        listeners = self.bus.ee.listeners("ggwave.disabled")
        self.assertTrue(len(listeners) > 0)

    # ------------------------------------------------------------------ #
    # handle_ggwave_on                                                     #
    # ------------------------------------------------------------------ #

    def test_handle_ggwave_on_sets_enabled_true(self) -> None:
        """handle_ggwave_on sets self.enabled = True."""
        msg = Message("ggwave.enabled")
        self.skill.handle_ggwave_on(msg)
        self.assertTrue(self.skill.enabled)

    def test_handle_ggwave_on_schedules_timeout_event(self) -> None:
        """handle_ggwave_on schedules a 'ggwave.timeout' event 15 minutes out."""
        self.skill.schedule_event = MagicMock()
        msg = Message("ggwave.enabled")
        self.skill.handle_ggwave_on(msg)
        self.skill.schedule_event.assert_called_once()
        call_kwargs = self.skill.schedule_event.call_args
        # Positional: handler, when, name
        args = call_kwargs[1] if call_kwargs[1] else {}
        all_args = list(call_kwargs[0]) + list(args.values())
        self.assertIn("ggwave.timeout", all_args)

    # ------------------------------------------------------------------ #
    # handle_ggwave_off                                                    #
    # ------------------------------------------------------------------ #

    def test_handle_ggwave_off_sets_enabled_false(self) -> None:
        """handle_ggwave_off sets self.enabled = False."""
        self.skill.enabled = True
        msg = Message("ggwave.disabled")
        self.skill.handle_ggwave_off(msg)
        self.assertFalse(self.skill.enabled)

    def test_handle_ggwave_off_from_already_disabled_is_idempotent(self) -> None:
        """handle_ggwave_off when already disabled keeps enabled = False."""
        self.skill.enabled = False
        msg = Message("ggwave.disabled")
        self.skill.handle_ggwave_off(msg)
        self.assertFalse(self.skill.enabled)

    # ------------------------------------------------------------------ #
    # handle_enable_ggwave                                                 #
    # ------------------------------------------------------------------ #

    def test_handle_enable_ggwave_when_disabled_emits_enable_message(self) -> None:
        """handle_enable_ggwave emits 'ovos.ggwave.enable' when not already enabled."""
        emitted: list[Message] = []
        self.bus.on("ovos.ggwave.enable", lambda m: emitted.append(m))

        self.skill.enabled = False
        self.skill.speak_dialog = MagicMock()
        msg = Message("recognizer_loop:utterance", {"utterances": ["enable ggwave"]})
        self.skill.handle_enable_ggwave(msg)

        self.assertEqual(len(emitted), 1)
        self.skill.speak_dialog.assert_called_once_with("ggwave_enabled")

    def test_handle_enable_ggwave_when_already_enabled_speaks_already_enabled(
        self,
    ) -> None:
        """handle_enable_ggwave speaks 'ggwave.already.enabled' when already active."""
        self.skill.enabled = True
        self.skill.speak_dialog = MagicMock()
        self.bus.emit = MagicMock(wraps=self.bus.emit)

        msg = Message("recognizer_loop:utterance", {"utterances": ["enable ggwave"]})
        self.skill.handle_enable_ggwave(msg)

        self.skill.speak_dialog.assert_called_once_with("ggwave_already_enabled")
        # ovos.ggwave.enable must NOT be emitted
        forwarded_types = [c.args[0].msg_type for c in self.bus.emit.call_args_list]
        self.assertNotIn("ovos.ggwave.enable", forwarded_types)

    # ------------------------------------------------------------------ #
    # handle_disable_ggwave                                                #
    # ------------------------------------------------------------------ #

    def test_handle_disable_ggwave_when_enabled_emits_disable_message(self) -> None:
        """handle_disable_ggwave emits 'ovos.ggwave.disable' when currently enabled."""
        emitted: list[Message] = []
        self.bus.on("ovos.ggwave.disable", lambda m: emitted.append(m))

        self.skill.enabled = True
        self.skill.speak_dialog = MagicMock()
        self.skill.cancel_scheduled_event = MagicMock()

        msg = Message("recognizer_loop:utterance", {"utterances": ["disable ggwave"]})
        self.skill.handle_disable_ggwave(msg)

        self.assertEqual(len(emitted), 1)
        self.skill.speak_dialog.assert_called_once_with("ggwave_disabled")

    def test_handle_disable_ggwave_when_enabled_cancels_timeout(self) -> None:
        """handle_disable_ggwave cancels the 'ggwave.timeout' scheduled event."""
        self.skill.enabled = True
        self.skill.speak_dialog = MagicMock()
        self.skill.cancel_scheduled_event = MagicMock()

        msg = Message("recognizer_loop:utterance", {"utterances": ["disable ggwave"]})
        self.skill.handle_disable_ggwave(msg)

        self.skill.cancel_scheduled_event.assert_called_once_with("ggwave.timeout")

    def test_handle_disable_ggwave_when_already_disabled_speaks_already_disabled(
        self,
    ) -> None:
        """handle_disable_ggwave speaks 'ggwave.already.disabled' when not active."""
        self.skill.enabled = False
        self.skill.speak_dialog = MagicMock()
        self.bus.emit = MagicMock(wraps=self.bus.emit)

        msg = Message("recognizer_loop:utterance", {"utterances": ["disable ggwave"]})
        self.skill.handle_disable_ggwave(msg)

        self.skill.speak_dialog.assert_called_once_with("ggwave_already_disabled")
        forwarded_types = [c.args[0].msg_type for c in self.bus.emit.call_args_list]
        self.assertNotIn("ovos.ggwave.disable", forwarded_types)

    # ------------------------------------------------------------------ #
    # bus event round-trip                                                 #
    # ------------------------------------------------------------------ #

    def test_ggwave_enabled_bus_event_sets_enabled_true(self) -> None:
        """Emitting 'ggwave.enabled' on the bus sets skill.enabled via event handler."""
        self.skill.enabled = False
        self.bus.emit(Message("ggwave.enabled"))
        # FakeBus delivers synchronously
        self.assertTrue(self.skill.enabled)

    def test_ggwave_disabled_bus_event_sets_enabled_false(self) -> None:
        """Emitting 'ggwave.disabled' on the bus sets skill.enabled via event handler."""
        self.skill.enabled = True
        self.bus.emit(Message("ggwave.disabled"))
        self.assertFalse(self.skill.enabled)

    # ------------------------------------------------------------------ #
    # persona install                                                      #
    # ------------------------------------------------------------------ #

    def test_initialize_registers_persona_install_event(self) -> None:
        """GGWaveSkill.initialize registers 'ovos.persona.install.index' bus event."""
        listeners = self.bus.ee.listeners("ovos.persona.install.index")
        self.assertTrue(len(listeners) > 0)

    def test_handle_install_index_fetches_persona_and_installs(self) -> None:
        """handle_install_index fetches persona data and installs it."""
        persona_json = json.dumps(
            {
                "name": "TestPersona",
                "description": "A test persona",
                "catch_phrase": "Hello from test!",
                "solvers": ["ovos-solver-hello-plugin"],
            }
        )
        mock_response = MagicMock()
        mock_response.text = persona_json
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            with patch("builtins.open", mock_open()):
                with patch("os.makedirs", return_value=None):
                    msg = Message("ovos.persona.install.index", data={"index": 0})
                    self.skill.speak = MagicMock()
                    self.skill.bus.emit = MagicMock()
                    self.skill.handle_install_index(msg)

                    # Should emit pip install message for the solver
                    emit_calls = self.bus.emit.call_args_list
                    pip_install_calls = [
                        c for c in emit_calls if c[0][0].msg_type == "ovos.pip.install"
                    ]
                    self.assertEqual(len(pip_install_calls), 1)
                    self.assertIn(
                        "ovos-solver-hello-plugin",
                        pip_install_calls[0][0][0].data["packages"],
                    )

                    # Should speak the catch_phrase
                    self.skill.speak.assert_called_once_with("Hello from test!")

    def test_handle_install_index_with_invalid_index_logs_error(self) -> None:
        """handle_install_index with out-of-range index logs error and does nothing."""
        mock_response = MagicMock()
        mock_response.text = '{"name": "Test"}'
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            msg = Message("ovos.persona.install.index", data={"index": 999})
            self.skill.log.error = MagicMock()
            self.skill.handle_install_index(msg)
            self.skill.log.error.assert_called_with("Invalid persona index: 999")

    def test_handle_install_index_with_negative_index_logs_error(self) -> None:
        """handle_install_index with negative index logs error and does nothing."""
        mock_response = MagicMock()
        mock_response.text = '{"name": "Test"}'
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            msg = Message("ovos.persona.install.index", data={"index": -1})
            self.skill.log.error = MagicMock()
            self.skill.handle_install_index(msg)
            self.skill.log.error.assert_called_with("Invalid persona index: -1")

    def test_handle_install_index_skips_failure_solver(self) -> None:
        """handle_install_index skips installation of failure solver plugin."""
        persona_json = json.dumps(
            {
                "name": "TestPersona",
                "description": "A test persona",
                "catch_phrase": "Hello!",
                "solvers": ["ovos-solver-failure-plugin", "ovos-solver-real-plugin"],
            }
        )
        mock_response = MagicMock()
        mock_response.text = persona_json
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            with patch("builtins.open", unittest.mock.mock_open()):
                with patch("os.makedirs", return_value=None):
                    msg = Message("ovos.persona.install.index", data={"index": 0})
                    self.skill.bus.emit = MagicMock()
                    self.skill.handle_install_index(msg)

                    # Should only emit pip install for the real solver
                    emit_calls = self.bus.emit.call_args_list
                    pip_calls = [
                        c for c in emit_calls if c[0][0].msg_type == "ovos.pip.install"
                    ]
                    self.assertEqual(len(pip_calls), 1)
                    self.assertIn(
                        "ovos-solver-real-plugin", pip_calls[0][0][0].data["packages"]
                    )
                    self.assertNotIn("failure", pip_calls[0][0][0].data["packages"][0])

    def test_install_persona_without_name_logs_error(self) -> None:
        """_install_persona with missing name logs error and returns early."""
        self.skill.log.error = MagicMock()
        self.skill._install_persona({})
        self.skill.log.error.assert_called_with("Persona data missing 'name'")

    def test_install_persona_speaks_default_when_no_catch_phrase(self) -> None:
        """_install_persona speaks default message when catch_phrase is not provided."""
        persona_data = {"name": "TestPersona", "solvers": []}
        self.skill.speak = MagicMock()
        self.skill.bus.emit = MagicMock()

        with patch("os.makedirs", return_value=None):
            with patch("builtins.open", unittest.mock.mock_open()):
                self.skill._install_persona(persona_data)

        self.skill.speak.assert_called_with(
            "Persona TestPersona has been installed and is ready for use."
        )

    def test_install_persona_saves_json_file(self) -> None:
        """_install_persona saves persona data as JSON file (without description)."""
        persona_data = {
            "name": "TestPersona",
            "description": "Should be removed",
            "catch_phrase": "Hi!",
            "solvers": [],
        }
        self.skill.bus.emit = MagicMock()

        with patch("os.makedirs", return_value=None):
            with patch("builtins.open", mock_open()):
                with patch("json.dump") as mock_json_dump:
                    self.skill._install_persona(persona_data)
                    mock_json_dump.assert_called_once()
                    # Verify description is not in saved data
                    saved_data = mock_json_dump.call_args[0][0]
                    self.assertNotIn("description", saved_data)

    def test_install_persona_emits_audio_play_sound(self) -> None:
        """_install_persona emits mycroft.audio.play_sound after installation."""
        persona_data = {"name": "TestPersona", "solvers": []}
        self.skill.speak = MagicMock()
        emitted: list[Message] = []
        self.bus.on("mycroft.audio.play_sound", lambda m: emitted.append(m))

        with patch("os.makedirs", return_value=None):
            with patch("builtins.open", unittest.mock.mock_open()):
                self.skill._install_persona(persona_data)

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].data["uri"], "snd/acknowledge.mp3")


if __name__ == "__main__":
    unittest.main()

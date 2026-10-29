"""
End-to-end tests for persona installation via ovos.persona.install.index using ovoscope.

This tests the flow where:
1. User triggers persona installation via ovos.persona.install.index message
2. GGWaveSkill receives the message and fetches persona data from store (mocked)
3. Persona config is saved
4. ovos.pip.install messages are emitted for each solver dependency

Setup pattern:
  - MiniCroft is started with GGWaveSkill loaded via skill_ids
  - Mock persona store is used to avoid network calls
  - PIP installation messages are captured and verified via CaptureSession
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import patch, MagicMock, PropertyMock

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_utils.log import LOG

from ovoscope import get_minicroft, CaptureSession

# Try to import ggwave skill - tests will skip if not available
try:
    from ovos_skill_ggwave import GGWaveSkill
    GGWAVE_AVAILABLE = True
except ImportError:
    GGWAVE_AVAILABLE = False

SKILL_ID = "ovos-skill-ggwave.openvoiceos"


class MockPersonaStore:
    """Mock persona marketplace data."""
    
    PERSONAS = [
        {
            "name": "TestBot",
            "description": "A test persona for development",
            "catch_phrase": "I am TestBot, ready to help!",
            "solvers": [
                "ovos-solver-wikipedia-plugin",
                "ovos-solver-failure-plugin"
            ]
        },
        {
            "name": "AssistantBot",
            "description": "Helpful assistant persona",
            "catch_phrase": "How can I assist you today?",
            "solvers": [
                "ovos-solver-ddg-plugin",
                "ovos-solver-wordnet-plugin",
                "ovos-solver-failure-plugin"
            ]
        }
    ]
    
    @classmethod
    def get_persona(cls, index: int) -> dict:
        """Get persona by index."""
        if 0 <= index < len(cls.PERSONAS):
            return cls.PERSONAS[index]
        raise IndexError(f"Invalid persona index: {index}")
    
    @classmethod
    def get_jsonl(cls) -> str:
        """Get personas as JSONL format (simulating remote store)."""
        return "\n".join(json.dumps(p) for p in cls.PERSONAS)


def _make_message(utterance_data: dict, session: Session = None) -> Message:
    """Helper to create a message with optional session."""
    context = {}
    if session:
        context["session"] = session.serialize()
    return Message(
        "ovos.persona.install.index",
        data=utterance_data,
        context=context
    )


class TestPersonaInstallE2E(TestCase):
    """E2E tests for ovos.persona.install.index message handling using ovoscope."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        LOG.set_level("WARNING")
        if not GGWAVE_AVAILABLE:
            raise unittest.SkipTest("ovos-skill-ggwave not installed")
        
        # Start MiniCroft with GGWaveSkill injected directly (no need to install as plugin)
        cls.minicroft = get_minicroft(
            skill_ids=[],  # No installed skills needed
            extra_skills={SKILL_ID: GGWaveSkill}  # Inject GGWaveSkill class directly
        )
        
        # Get the skill instance from plugin_skills dict (PluginSkillLoader has .instance attribute)
        loader = cls.minicroft.plugin_skills.get(SKILL_ID)
        if not loader:
            raise RuntimeError(f"GGWaveSkill not loaded! Available: {list(cls.minicroft.plugin_skills.keys())}")
        cls.skill = loader.instance
        
        if not cls.skill:
            raise RuntimeError(f"GGWaveSkill instance not ready!")
        
        # Mock settings to avoid initialization issues
        cls.mock_settings = {"persona_store_url": "https://example.com/personas.jsonl"}
        cls.settings_patcher = patch.object(type(cls.skill), 'settings', new_callable=PropertyMock, return_value=cls.mock_settings)
        cls.settings_patcher.start()
        
        # Mock requests.get for all tests
        cls.requests_patcher = patch('ovos_skill_ggwave.requests.get')
        cls.mock_get = cls.requests_patcher.start()
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = MockPersonaStore.get_jsonl()
        mock_response.raise_for_status = MagicMock()
        cls.mock_get.return_value = mock_response
    
    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        if hasattr(cls, 'settings_patcher'):
            cls.settings_patcher.stop()
        if hasattr(cls, 'requests_patcher'):
            cls.requests_patcher.stop()
        if hasattr(cls, 'minicroft'):
            cls.minicroft.stop()
    
    def setUp(self):
        """Reset mock call history before each test."""
        self.mock_get.reset_mock()
    
    def test_install_persona_index_0_e2e(self):
        """Install persona at index 0 → emits ovos.pip.install for wikipedia solver.
        
        E2E test using ovoscope CaptureSession to verify the complete message flow.
        """
        session = Session("test-persona-install-0")
        session.lang = "en-US"
        
        # Create the persona installation message
        install_msg = _make_message({"index": "0"}, session)
        
        # Use CaptureSession to capture all messages during the interaction
        capture = CaptureSession(self.minicroft)
        
        # Emit the installation message and capture responses
        capture.capture(install_msg, timeout=10)
        
        # Get captured messages
        messages = capture.finish()
        
        # Verify the mock was called
        self.mock_get.assert_called_once()
        
        # Verify ovos.pip.install was emitted for wikipedia solver
        pip_messages = [m for m in messages if m.msg_type == "ovos.pip.install"]
        self.assertEqual(len(pip_messages), 1, f"Expected 1 pip.install message, got {len(pip_messages)}")
        self.assertEqual(
            pip_messages[0].data["packages"],
            ["ovos-solver-wikipedia-plugin"]
        )
    
    def test_install_persona_index_1_e2e(self):
        """Install persona at index 1 → emits ovos.pip.install for 2 solvers."""
        session = Session("test-persona-install-1")
        session.lang = "en-US"
        
        install_msg = _make_message({"index": "1"}, session)
        
        capture = CaptureSession(self.minicroft)
        capture.capture(install_msg, timeout=10)
        messages = capture.finish()
        
        # Verify ovos.pip.install was emitted for ddg and wordnet solvers
        pip_messages = [m for m in messages if m.msg_type == "ovos.pip.install"]
        self.assertEqual(len(pip_messages), 2, f"Expected 2 pip.install messages, got {len(pip_messages)}")
        
        # Check both solvers were requested
        packages = []
        for msg in pip_messages:
            packages.extend(msg.data["packages"])
        
        self.assertIn("ovos-solver-ddg-plugin", packages)
        self.assertIn("ovos-solver-wordnet-plugin", packages)
        # failure-plugin should NOT be in the list
        self.assertNotIn("ovos-solver-failure-plugin", packages)
    
    def test_install_persona_invalid_index_e2e(self):
        """Install persona with invalid index → no pip installs."""
        session = Session("test-persona-install-invalid")
        session.lang = "en-US"
        
        install_msg = _make_message({"index": "999"}, session)
        
        capture = CaptureSession(self.minicroft)
        capture.capture(install_msg, timeout=10)
        messages = capture.finish()
        
        # Verify no pip install messages were emitted
        pip_messages = [m for m in messages if m.msg_type == "ovos.pip.install"]
        self.assertEqual(len(pip_messages), 0, f"Expected 0 pip.install messages, got {len(pip_messages)}")
    
    def test_install_persona_network_error_e2e(self):
        """Install persona when network fails → no pip installs."""
        # Mock network error
        self.mock_get.side_effect = Exception("Network error")
        
        session = Session("test-persona-install-network-error")
        session.lang = "en-US"
        
        install_msg = _make_message({"index": "0"}, session)
        
        capture = CaptureSession(self.minicroft)
        capture.capture(install_msg, timeout=10)
        messages = capture.finish()
        
        # Verify no pip install messages were emitted
        pip_messages = [m for m in messages if m.msg_type == "ovos.pip.install"]
        self.assertEqual(len(pip_messages), 0, f"Expected 0 pip.install messages, got {len(pip_messages)}")

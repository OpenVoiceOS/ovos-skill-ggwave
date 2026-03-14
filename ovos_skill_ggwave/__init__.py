import datetime
import json
import os
import requests
from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_config.locations import get_xdg_config_save_path
from ovos_bus_client.message import Message


class GGWaveSkill(OVOSSkill):
    def initialize(self):
        self.add_event("ggwave.enabled", self.handle_ggwave_on)
        self.add_event("ggwave.disabled", self.handle_ggwave_off)

        # Persona Installation Events
        self.add_event("ovos.persona.install.index", self.handle_install_index)

        self.enabled = False

    @property
    def persona_store_url(self):
        return (
            self.settings.get("persona_store_url")
            or "https://raw.githubusercontent.com/TigreGotico/ovos-persona-marketplace/master/personas.jsonl"
        )

    def handle_ggwave_on(self, message):
        self.enabled = True
        self.schedule_event(
            handler=self.handle_ggwave_off,
            when=datetime.datetime.now() + datetime.timedelta(minutes=15),
            name="ggwave.timeout",
        )

    def handle_ggwave_off(self, message):
        self.enabled = False

    @intent_handler("enable.ggwave.intent")
    def handle_enable_ggwave(self, message):
        if not self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.enable"))
            self.speak_dialog("ggwave.enabled")
        else:
            self.speak_dialog("ggwave.already.enabled")

    @intent_handler("disable.ggwave.intent")
    def handle_disable_ggwave(self, message):
        if self.enabled:
            self.bus.emit(message.forward("ovos.ggwave.disable"))
            self.cancel_scheduled_event("ggwave.timeout")
            self.speak_dialog("ggwave.disabled")
        else:
            self.speak_dialog("ggwave.already.disabled")

    def handle_install_index(self, message):
        index = int(message.data.get("index", -1))
        self.log.info(f"Installing persona at index: {index}")

        try:
            response = requests.get(self.persona_store_url)
            response.raise_for_status()
            lines = response.text.strip().split("\n")
            if 0 <= index < len(lines):
                persona_data = json.loads(lines[index])
                self._install_persona(persona_data)
            else:
                self.log.error(f"Invalid persona index: {index}")
        except Exception as e:
            self.log.exception(f"Failed to fetch persona from store: {e}")

    def _install_persona(self, persona_data):
        name = persona_data.get("name")
        if not name:
            self.log.error("Persona data missing 'name'")
            return

        # 1. Save persona.json
        config_path = get_xdg_config_save_path("ovos_persona")
        os.makedirs(config_path, exist_ok=True)

        # Clean description for the file, keep catch_phrase
        clean_data = {k: v for k, v in persona_data.items() if k != "description"}

        file_path = os.path.join(config_path, f"{name}.json")
        with open(file_path, "w") as f:
            json.dump(clean_data, f, indent=2)

        self.log.info(f"Persona saved to: {file_path}")

        # 2. Install solver dependencies
        solvers = persona_data.get("solvers", [])
        for solver in solvers:
            if solver == "ovos-solver-failure-plugin":
                continue

            # Assume the plugin name is the pip package name
            self.log.info(f"Requesting installation of solver: {solver}")
            self.bus.emit(Message("ovos.pip.install", {"packages": [solver]}))

        # 3. Confirmation
        # Speak catch_phrase to acknowledge install worked
        catch_phrase = persona_data.get("catch_phrase")
        if catch_phrase:
            self.speak(catch_phrase)
        else:
            self.speak(f"Persona {name} has been installed and is ready for use.")

        self.bus.emit(
            Message("mycroft.audio.play_sound", {"uri": "snd/acknowledge.mp3"})
        )

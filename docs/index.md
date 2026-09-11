# ovos-skill-ggwave

Voice interface for the [ggwave](https://github.com/ggerganov/ggwave) audio-data-over-sound plugin.

ggwave encodes binary data as audible tones (audio QR codes) that nearby devices can decode.
This skill lets users enable and disable ggwave transmission with voice commands. A 15-minute
timeout disables ggwave automatically, so it does not stay on indefinitely.

## Architecture

```
User utterance
     │
     ▼
Padatious pipeline
     │
     ├─ enable.ggwave.intent ──► GGWaveSkill.handle_enable_ggwave
     │                               emit ovos.ggwave.enable
     │                               speak "ggwave.enabled" dialog
     │                               schedule ggwave.timeout (+15 min)
     │
     └─ disable.ggwave.intent ─► GGWaveSkill.handle_disable_ggwave
                                     emit ovos.ggwave.disable
                                     speak "ggwave.disabled" dialog
                                     cancel ggwave.timeout
```

## Key Classes

| Class | File | Description |
|---|---|---|
| `GGWaveSkill` | `__init__.py:8` | Main skill class. Manages enabled state and bus events |

## Intent Handlers

| Handler | Intent file | Trigger examples |
|---|---|---|
| `GGWaveSkill.handle_enable_ggwave` (`__init__.py:26`) | `enable.ggwave.intent` | "enable ggwave", "start audio codes", "ggwave on" |
| `GGWaveSkill.handle_disable_ggwave` (`__init__.py:34`) | `disable.ggwave.intent` | "disable ggwave", "stop audio codes", "ggwave off" |

## Bus Events

| Message type | Direction | Description |
|---|---|---|
| `ggwave.enabled` | inbound | External signal that ggwave became active |
| `ggwave.disabled` | inbound | External signal that ggwave became inactive |
| `ovos.ggwave.enable` | outbound | Forwarded to ggwave plugin to start transmission |
| `ovos.ggwave.disable` | outbound | Forwarded to ggwave plugin to stop transmission |

## State

`GGWaveSkill.enabled` (`__init__.py:13`) is a boolean that tracks whether ggwave is active.
Both the bus event handlers and the intent handlers update it.

## Locales

Supported: `ca-es`, `da-dk`, `de-de`, `es-es`, `eu`, `gl-es`, `it-it`, `pt-br`, `en-us`.

## Testing

- **Unit tests**: `test/unittests/test_skill.py`. Uses FakeBus to test handler logic in isolation
- **End-to-end tests**: `test/end2end/test_ggwave.py`. Uses ovoscope to test the full intent and message sequence

```bash
# Unit tests
uv run pytest test/unittests/ -v --cov=ovos_skill_ggwave --cov-report=term-missing

# End-to-end tests
uv run pytest test/end2end/ -v --timeout=60
```

## Related

- [ggwave project](https://github.com/ggerganov/ggwave)
- [ovos-plugin-manager: opm.plugin.skill entry point](https://github.com/OpenVoiceOS/ovos-plugin-manager)

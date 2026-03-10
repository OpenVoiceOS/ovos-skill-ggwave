# FAQ — ovos-skill-ggwave

## What is ggwave?

ggwave encodes binary data as audible tones — sometimes called "audio QR codes". Nearby devices
running a ggwave decoder can receive the data without any network connection. This skill provides
a voice interface for the OVOS ggwave plugin.

## How do I enable ggwave by voice?

Say any of:
- "enable ggwave"
- "start audio codes"
- "allow audio QR codes"
- "ggwave on"

The skill will confirm and automatically disable ggwave after 15 minutes
(`GGWaveSkill.handle_ggwave_on` — `__init__.py:16`).

## How do I disable ggwave by voice?

Say any of:
- "disable ggwave"
- "stop audio data"
- "ggwave off"

The skill confirms and cancels the 15-minute timeout
(`GGWaveSkill.handle_disable_ggwave` — `__init__.py:34`).

## Why does ggwave auto-disable after 15 minutes?

To prevent leaving audio data transmission running indefinitely. The timeout is scheduled in
`GGWaveSkill.handle_ggwave_on` (`__init__.py:17`) via `self.schedule_event` with a 15-minute
`datetime.timedelta`.

## What bus messages does the skill emit?

| Message | When |
|---|---|
| `ovos.ggwave.enable` | User says "enable ggwave" and ggwave is not already on |
| `ovos.ggwave.disable` | User says "disable ggwave" and ggwave is currently on |

## What bus messages does the skill listen to?

| Message | Handler |
|---|---|
| `ggwave.enabled` | `GGWaveSkill.handle_ggwave_on` — `__init__.py:15` |
| `ggwave.disabled` | `GGWaveSkill.handle_ggwave_off` — `__init__.py:23` |

## What happens if I say "enable ggwave" when it is already enabled?

The skill speaks "audio QR codes already enabled" (dialog `ggwave.already.enabled`) and does
not emit `ovos.ggwave.enable` again
(`GGWaveSkill.handle_enable_ggwave` — `__init__.py:26`).

## What happens if I say "disable ggwave" when it is already disabled?

The skill speaks "disabling audio QR codes already disabled" (dialog `ggwave.already.disabled`)
and does not emit `ovos.ggwave.disable`
(`GGWaveSkill.handle_disable_ggwave` — `__init__.py:34`).

## Which languages are supported?

Catalan (ca-es), Danish (da-dk), German (de-de), Spanish (es-es), Basque (eu), Galician (gl-es),
Italian (it-it), Portuguese Brazil (pt-br), English (en-us).

## How do I run the tests?

```bash
# Unit tests (FakeBus, handler logic)
uv run pytest test/unittests/ -v --cov=ovos_skill_ggwave --cov-report=term-missing

# End-to-end tests (ovoscope, full intent + message sequence)
uv run pytest test/end2end/ -v --timeout=60
```

## How is the skill installed?

```bash
uv pip install -e Skills/ovos-skill-ggwave/
# Verify plugin registration:
python -c "from ovos_plugin_manager.skills import find_skill_plugins; print(list(find_skill_plugins()))"
```

The entry point group is `ovos.plugin.skill`; the skill ID is `ovos-skill-ggwave.openvoiceos`.

## What is the skill ID?

`ovos-skill-ggwave.openvoiceos` (defined in `setup.py:19–21`).

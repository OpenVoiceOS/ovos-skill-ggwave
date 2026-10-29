# SUGGESTIONS — ovos-skill-ggwave

## SUG-001 — Persist `enabled` state across restarts

`GGWaveSkill.initialize` (`__init__.py:10`) always resets `self.enabled = False`.
Use `self.settings` to persist state:

```python
def initialize(self) -> None:
    self.add_event("ggwave.enabled", self.handle_ggwave_on)
    self.add_event("ggwave.disabled", self.handle_ggwave_off)
    self.enabled = self.settings.get("enabled", False)
```

And update `self.settings["enabled"]` in the handlers. This way ggwave survives an OVOS restart
within the 15-minute window.

## SUG-002 — Make the timeout duration configurable via settingsmeta.json

Hard-coded 15-minute timeout (`__init__.py:19`) is not user-adjustable. A `settingsmeta.json`
with a `timeout_minutes` field would let users tune this without code changes.

## SUG-003 — Migrate `setup.py` to `pyproject.toml`

Standard OVOS packaging (CLAUDE.md §2). The migration is straightforward given the simple
`setup.py` structure.

## SUG-004 — Add missing gh-automations CI/CD workflows

Add all standard workflows from `OpenVoiceOS/gh-automations@dev`:
`test.yml`, `ovoscope.yml`, `build-tests.yml`, `lint.yml`, `license-check.yml`, `pip-audit.yml`,
`skill-check.yml`, `publish-alpha.yml`, `publish-stable.yml`, `python-support.yml`,
`repo-health.yml`.

Use the `/ovos-workflows-adder` skill to add them automatically.

## SUG-005 — Add type hints and docstrings to `__init__.py`

All five methods in `GGWaveSkill` (`__init__.py:10–41`) lack type annotations and docstrings,
violating the mandatory workspace coding standard.

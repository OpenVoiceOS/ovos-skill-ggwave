# QUICK_FACTS — ovos-skill-ggwave

| Field | Value |
|---|---|
| **Package name** | `ovos-skill-ggwave` |
| **Skill ID** | `ovos-skill-ggwave.openvoiceos` |
| **Entry point group** | `ovos.plugin.skill` |
| **Main class** | `GGWaveSkill` — `__init__.py:8` |
| **Intent pipeline** | Padatious |
| **Intents** | `enable.ggwave.intent`, `disable.ggwave.intent` |
| **Outbound messages** | `ovos.ggwave.enable`, `ovos.ggwave.disable` |
| **Inbound messages** | `ggwave.enabled`, `ggwave.disabled` |
| **Auto-timeout** | 15 minutes after enable |
| **Locales** | ca-es, da-dk, de-de, es-es, eu, gl-es, it-it, pt-br, en-us |
| **License** | Apache 2.0 |
| **Tests (unit)** | `test/unittests/test_skill.py` |
| **Tests (E2E)** | `test/end2end/test_ggwave.py` (requires `ovos-padatious`) |
| **Docs** | `docs/index.md` |
| **Test dependencies** | `ovoscope`, `ovos-padatious` |

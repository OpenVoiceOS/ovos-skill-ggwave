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

## CI/CD Workflows

| Workflow | Purpose |
|----------|---------|
| `build-tests.yml` | Build/install/test matrix across Python 3.10–3.14 |
| `coverage.yml` | Pytest coverage report (deploys to GitHub Pages) |
| `lint.yml` | Ruff linting |
| `license_check.yml` | License compliance check |
| `pip_audit.yml` | Security vulnerability scan |
| `ovoscope.yml` | End-to-end skill tests with Padatious |
| `skill-check.yml` | Locale coverage, skill.json validity, gitlocalize readiness |
| `locale-check.yml` | Verifies locale files are included in package build |
| `repo-health.yml` | Required files check, version block validation |
| `release-preview.yml` | Next version prediction from PR labels |
| `release_workflow.yml` | Alpha release on PR merge to `dev` |
| `publish_stable.yml` | Stable release on PR merge to `master` |
| `sync-translations.yml` | Sync gitlocalize translation commits |
| `conventional-label.yml` | Auto-label PRs by commit type |

## Translation Management

- **Locale path**: `ovos_skill_ggwave/locale/`
- **Translations path**: `translations/`
- **Sync script**: `scripts/sync_translations.py`
- **Prepare script**: `scripts/prepare_translations.py`
- **GitLocalize**: Enabled — auto-sync on push from `gitlocalize-app[bot]`

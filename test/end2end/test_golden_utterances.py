"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

Each locale must pass at least ``MIN_MATCH_RATE`` of its rows, and each
intent at least ``MIN_MATCHED_ROWS_PER_INTENT`` of its own rows. All rows run,
including rows marked ``needs_manual`` or ``machine_generated``, and the test
prints every row that misses with the intent that matched instead.

``negative_utterances_<lang>.jsonl`` holds requests for other skills (weather,
timers, music, time, jokes, volume). In a MiniCroft of their own, each one
must match none of this skill's intents, unless ``NEGATIVE_KNOWN_CLAIMS``
names that claim. A locale in ``NEGATIVE_ENGINE_GAPS`` runs its negatives as
a non-strict expected failure, with the measured reason.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-ggwave.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# Every intent with rows in a locale must match at least this many of them,
# so the locale rate cannot hide an intent that never matches.
MIN_MATCHED_ROWS_PER_INTENT = 1
# A negative row that m2v claims in two runs is listed here by name, as
# {lang: {utterance: claimed_intent}}. Any other claim fails the locale.
NEGATIVE_KNOWN_CLAIMS = {
    "ru-RU": {"включи музыку": "enable_ggwave"},
}
# Locales whose negatives the published m2v model cannot separate from this
# skill, as {lang: reason}. Their negatives run as a non-strict expected failure.
NEGATIVE_ENGINE_GAPS = {}
# A locale that stays below MIN_MATCH_RATE on the published m2v model with the
# lines it ships, as {lang: (measured rate, reason)}.
# Its rate check is an expected failure, but the per-intent floor still holds,
# and a rate more than GAP_TOLERANCE below the measured rate fails.
GOLDEN_LOCALE_GAPS = {
    "es-CO": (0.667, "m2v confuses es-CO enable and disable rows and matches 2 disable "
                     "rows to nothing; 8 of 12 rows match in each of three runs"),
    "fa-IR": (0.75, "m2v confuses fa-IR enable and disable rows and matches 1 disable "
                    "row to nothing; 9 of 12 rows match in each of three runs"),
}
GAP_TOLERANCE = 0.10
END2END_DIR = Path(__file__).parent
LOCALE_ROOT = END2END_DIR.parents[1] / "ovos_skill_ggwave" / "locale"
DEFAULT_LANG_AT_IMPORT = SessionManager.get_default_session().lang


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVES = _rows_by_lang("negative_utterances")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


def _boot(lang):
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    warm_m2v_models(minicroft)
    return minicroft, minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    minicroft, engine = _boot(lang)
    try:
        misses = []
        matched = Counter()
        for row in ROWS[lang]:
            expected = f"{SKILL_ID}:{row['intent_label'].removesuffix('.intent')}"
            got = _matched_intent(engine, row["utterance"], lang)
            if got == expected:
                matched[row["intent_label"]] += 1
            else:
                misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
    finally:
        minicroft.stop()
    rate = 1 - len(misses) / len(ROWS[lang])
    print(f"[{lang}] {rate:.1%} of {len(ROWS[lang])} rows match", *misses, sep="\n  ")
    starved = sorted(label for label in {row["intent_label"] for row in ROWS[lang]}
                     if matched[label] < MIN_MATCHED_ROWS_PER_INTENT)
    assert not starved, (
        f"[{lang}] intents with fewer than {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    if lang in GOLDEN_LOCALE_GAPS:
        measured, reason = GOLDEN_LOCALE_GAPS[lang]
        assert rate >= measured - GAP_TOLERANCE, (
            f"[{lang}] {rate:.1%} of rows match, more than {GAP_TOLERANCE:.0%} below "
            f"the measured {measured:.1%}:\n  " + "\n  ".join(misses)
        )
        if rate < MIN_MATCH_RATE:
            pytest.xfail(f"[{lang}] {rate:.1%} of rows match: {reason}")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang], strict=False))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVES)
])
def test_negative_rows_match_no_skill_intent(lang):
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    minicroft, engine = _boot(lang)
    try:
        claimed = []
        for row in NEGATIVES[lang]:
            got = _matched_intent(engine, row["utterance"], lang)
            if got and got.startswith(f"{SKILL_ID}:") and \
                    f"{SKILL_ID}:{known.get(row['utterance'], '')}" != got:
                claimed.append(f"{row['utterance']!r}: claimed by {got}")
    finally:
        minicroft.stop()
    print(f"[{lang}] {len(claimed)} of {len(NEGATIVES[lang])} negatives claimed", *claimed, sep="\n  ")
    assert not claimed, f"[{lang}] negatives claimed by this skill:\n  " + "\n  ".join(claimed)


def test_every_negative_file_has_a_golden_file():
    assert set(NEGATIVES) <= set(ROWS), sorted(set(NEGATIVES) - set(ROWS))


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    shipping = {d.name for d in LOCALE_ROOT.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_every_locale_ships_every_intent_file():
    reference = {p.name for p in (LOCALE_ROOT / "en-US").rglob("*.intent")}
    missing = {d.name: sorted(reference - {p.name for p in d.rglob("*.intent")})
               for d in LOCALE_ROOT.iterdir() if d.is_dir()}
    missing = {lang: names for lang, names in missing.items() if names}
    assert not missing, missing


def test_every_golden_row_names_an_intent_its_locale_ships():
    unknown = [f"{lang}: {row['intent_label']}" for lang, rows in ROWS.items() for row in rows
               if not (LOCALE_ROOT / lang / row["intent_label"]).is_file()]
    assert not unknown, unknown


def test_the_module_leaves_the_process_on_its_default_language():
    """A MiniCroft booted in one locale writes the process default language
    back when it stops. If it did not, every MiniCroft booted later in the
    same pytest process would load the skill in the last locale and route
    nothing. This test runs after every locale and reads that value."""
    assert SessionManager.get_default_session().lang == DEFAULT_LANG_AT_IMPORT

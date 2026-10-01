"""Multilingual golden-utterance end-to-end coverage for
ovos-skill-ggwave.

Every locale under ``ovos_skill_ggwave/locale/`` gets its own
``golden_utterances_<lang>.jsonl``. Each row's utterance is a direct
mechanical expansion of that locale's own ``enable_ggwave.intent`` /
``disable_ggwave.intent`` padatious template: the ``(a|b|c)`` word-choice
groups are resolved to one alternative each, three distinct
combinations per intent, so every word in a row already exists in that
locale's own template file. No translation, no drafted prose.

One ``MiniCroft`` is booted per locale (class-scoped, torn down after),
mirroring ovos-skill-hello-world's multilang suite and
ovos-skill-date-time/test/end2end/test_intents_it_it.py on dev.

Run:
    uv run pytest test/end2end/test_golden_utterances_multilang.py -v
"""
import json
from pathlib import Path
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft, PADATIOUS_PIPELINE

from ovos_skill_ggwave import GGWaveSkill

SKILL_ID = "ovos-skill-ggwave.openvoiceos"

END2END_DIR = Path(__file__).parent

LANGS = [
    "en-US", "ca-ES", "da-DK", "de-DE", "es-ES", "eu-ES", "fr-FR",
    "gl-ES", "it-IT", "kab", "nl-NL", "pt-BR", "pt-PT", "sv-SE",
]

NEGATIVE_UTTERANCES = [
    ("what's the weather", "en-US", "ovos-skill-weather.openvoiceos"),
    ("play some music", "en-US", "ovos-skill-music.openvoiceos"),
    ("set a timer for 5 minutes", "en-US", "ovos-skill-alerts.openvoiceos"),
]


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _candidates(intent_label: str) -> set:
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{SKILL_ID}:{intent_label}", f"{SKILL_ID}:{base}"}


def _capture(mc, text, lang, session_id, pipeline=PADATIOUS_PIPELINE):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(pipeline)
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


KNOWN_BUGS = {}


def _make_locale_test_case(lang):
    rows = _load_rows(lang)
    negatives = [n for n in NEGATIVE_UTTERANCES if n[1] == lang]

    class _LocaleGoldenCase(TestCase):
        LANG = lang

        @classmethod
        def setUpClass(cls):
            cls.minicroft = get_minicroft(
                skill_ids=[], extra_skills={SKILL_ID: GGWaveSkill}, lang=lang
            )

        @classmethod
        def tearDownClass(cls):
            if getattr(cls, "minicroft", None):
                cls.minicroft.stop()

        def _check_row(self, row):
            candidates = _candidates(row["intent_label"])
            types = _capture(
                self.minicroft, row["utterance"], row["lang"],
                f"golden-{row['lang']}-{row['intent_label']}-{row['utterance']}",
            )
            matched = any(t in candidates for t in types)
            bug_key = (row["lang"], row["utterance"])
            if bug_key in KNOWN_BUGS and not matched:
                self.skipTest(f"known-bug: {KNOWN_BUGS[bug_key]}")
            self.assertTrue(
                matched,
                f"[{row['lang']}] {row['utterance']!r}: expected one of "
                f"{sorted(candidates)!r}, got {types!r}",
            )

        def _check_negative(self, text, source_skill):
            types = _capture(self.minicroft, text, lang, f"negative-{lang}-{text}",
                              pipeline=["ovos-padatious-pipeline-plugin-high"])
            claimed = any(t.startswith(f"{SKILL_ID}:") and t != f"{SKILL_ID}.activate"
                          for t in types)
            self.assertFalse(
                claimed, f"[{lang}] {text!r} was incorrectly claimed by {SKILL_ID}: {types!r}"
            )

    for i, row in enumerate(rows):
        def _test(self, row=row):
            self._check_row(row)
        _test.__name__ = f"test_golden_{i:03d}_{row['intent_label'].replace('.', '_')}"
        setattr(_LocaleGoldenCase, _test.__name__, _test)

    for i, (text, _lang, source_skill) in enumerate(negatives):
        def _neg_test(self, text=text, source_skill=source_skill):
            self._check_negative(text, source_skill)
        _neg_test.__name__ = f"test_negative_{i:03d}"
        setattr(_LocaleGoldenCase, _neg_test.__name__, _neg_test)

    _LocaleGoldenCase.__name__ = f"TestGolden_{lang.replace('-', '_')}"
    _LocaleGoldenCase.__qualname__ = _LocaleGoldenCase.__name__
    return _LocaleGoldenCase


for _lang in LANGS:
    _cls = _make_locale_test_case(_lang)
    globals()[_cls.__name__] = _cls
del _lang, _cls  # for-loop variables leak into module globals; without this
# deletion pytest also collects a spurious extra test class literally named
# "_cls" (bound to whichever locale ran last), which boots a second,
# redundant MiniCroft for that locale under a different collected name.

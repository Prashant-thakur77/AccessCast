"""Run the REAL description rules on a fixed set of example lines → src/accesscast/player/static/data/rule_examples.json.

The landing page's "Gemma proposes. Code decides." demo shows these results. They are real rule outputs computed
here, not hand-written; the context (pause, facts, dialogue) is the fixture's scene 2, stated on the page.
"""

from __future__ import annotations

import json

from accesscast.config import REPO_ROOT
from accesscast.schemas import (
    Budget,
    Character,
    Item,
    ItemKind,
    OnScreenText,
    SceneEvidence,
    Slot,
    VisibleFact,
    Word,
)
from accesscast.verify.base import VerifyContext, run_rules
from accesscast.verify.rules_ad import AD_RULES

EXAMPLES = [
    ("A good line", "On screen: Ctrl + C."),
    ("Invents a name", "Sarah presses Ctrl + C on her laptop."),
    ("Guesses a motive and a job", "A teacher presses Ctrl + C because she wants to copy the text."),
    ("Describes a sound", "The laptop beeps loudly as she presses a key."),
    ("Too long for the pause", "A person with short grey hair and a blue cardigan sits at a brown desk and reaches toward the laptop keyboard to press Ctrl and C."),
    ("Repeats the dialogue", "Press control and C to copy the text."),
    ("Says “we see”", "We see the screen showing Ctrl + C."),
]

words = [Word(i=i, w=w, start_ms=a, end_ms=b) for i, (w, a, b) in enumerate([
    ("Press", 7925, 8175), ("control", 8175, 8750), ("and", 8750, 8888), ("C", 8888, 9100), ("to", 9100, 9200),
    ("copy", 9200, 9550), ("the", 9550, 9688), ("text.", 9688, 10450)])]
ev = SceneEvidence(scene_id="SC002", frames=["f00.jpg", "f01.jpg"], frame_ms=[4400, 6000],
                   setting="A room with a beige wall and a brown desk.",
                   characters=[Character(cid="C0001", appearance="person with short grey hair and a blue cardigan")],
                   visible_facts=[VisibleFact(fid="F003", frames=[0, 1], text="The laptop screen shows Ctrl + C.", priority=1),
                                  VisibleFact(fid="F002", frames=[0], text="A person with short grey hair and a blue cardigan sits at a desk with a laptop.", priority=3)],
                   on_screen_text=[OnScreenText(text="Ctrl + C", frame=1, kind="slide", ocr_agrees=True)])
ctx = VerifyContext(lang="en", words=words, evidence={"SC002": ev}, guard_ms=120, wps_voice=2.6)
out = []
for label, text in EXAMPLES:
    it = Item(id="ad.en.demo", kind=ItemKind.AD, lang="en", audiences=["blind"], scene_id="SC002", gap_id="G0002",
              anchor_ms=4370, slot=Slot(start_ms=4370, end_ms=7805), budget=Budget(words_max=7, seconds_max=3.43, wps_voice=2.6),
              fact_ids=["F003", "F002"], draft=text)
    res = run_rules(it, ctx, AD_RULES)
    out.append({"label": label, "text": text, "ok": res.ok,
                "findings": [{"rule": f.rule, "severity": f.severity, "observed": f.observed, "threshold": f.threshold,
                              "message": f.message} for f in [*res.violations, *res.warnings]]})
dst = REPO_ROOT / "src" / "accesscast" / "player" / "static" / "data" / "rule_examples.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps({"context": {"pause_seconds": 3.43, "words_max": 7, "facts": [f.text for f in ev.visible_facts],
                                       "dialogue_after": "Press control and C to copy the text.",
                                       "note": "Real rule output on the demo fixture's second scene."}, "examples": out},
                          indent=1, ensure_ascii=False))
for o in out:
    print(o["ok"], o["label"], [f["rule"] for f in o["findings"]])

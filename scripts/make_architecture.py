"""docs/architecture.svg: what runs where (AMD Token Factory, our computer, code, a person, the viewer's browser).
Text only states how the system is built; no measured numbers. Usage: python scripts/make_architecture.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
W, H = 1600, 900
COL = {  # fill, text
    "amd": ("#E4402A", "#FFFFFF"),
    "pc": ("#1B1E4B", "#FFFFFF"),
    "code": ("#FFD23F", "#141B34"),
    "person": ("#1E7A4C", "#FFFFFF"),
    "browser": ("#12355B", "#FFFFFF"),
    "input": ("#E8E3D6", "#141B34"),
}
BOXES = [  # id, x, y, w, h, kind, title, lines
    ("video", 30, 380, 210, 110, "input", "Your video", ["dropped into Studio,", "or on our site"]),
    (
        "listen",
        280,
        140,
        340,
        190,
        "pc",
        "Listen",
        [
            "Whisper + forced alignment",
            "Silero VAD: where speech is",
            "AST: sound labels",
            "PySceneDetect: scenes",
        ],
    ),
    (
        "gaps",
        280,
        380,
        340,
        150,
        "code",
        "Plan",
        ["the pauses between words,", "which line goes where,", "the word budget"],
    ),
    (
        "gemma",
        670,
        140,
        430,
        290,
        "amd",
        "Gemma 4 31B · Token Factory",
        [
            "looks at frames, lists what it sees",
            "writes description from that list",
            "rewrites captions as easy-read",
            "translates: hi, it, es, fr",
            "writes voice-over lines",
            "repairs a line, told why",
        ],
    ),
    (
        "checks",
        670,
        480,
        430,
        200,
        "code",
        "Checks: code decides",
        [
            "every line, rule by rule: timing,",
            "numbers, names, negations, sounds,",
            "claims, language. A failed line goes",
            "back to Gemma with the reason.",
        ],
    ),
    (
        "person",
        1150,
        140,
        230,
        160,
        "person",
        "A person",
        ["reviews every line,", "keyboard only:", "approve, edit, reject"],
    ),
    (
        "render",
        1150,
        340,
        230,
        190,
        "pc",
        "Voice + render",
        ["Kokoro voices:", "en, hi, it, es, fr", "ffmpeg: mix, holds,", "loudness checks"],
    ),
    ("gate", 1150, 570, 230, 110, "code", "Render gate", ["refuses while a", "line still waits"]),
    (
        "viewer",
        1420,
        260,
        160,
        330,
        "browser",
        "Viewers",
        [
            "can't see",
            "can't hear",
            "simpler words",
            "हिन्दी",
            "Italiano",
            "Español",
            "Français",
            "",
            "player site",
        ],
    ),
]
ARROWS = [
    ("video", "listen"),
    ("video", "gaps"),
    ("listen", "gaps"),
    ("listen", "gemma"),
    ("gaps", "gemma"),
    ("gemma", "checks"),
    ("checks", "gemma"),
    ("checks", "person"),
    ("person", "render"),
    ("render", "gate"),
    ("gate", "viewer"),
    ("render", "viewer"),
]


def center(b: tuple) -> tuple[float, float]:
    return b[1] + b[3] / 2, b[2] + b[4] / 2


def edge(b: tuple, toward: tuple[float, float]) -> tuple[float, float]:
    cx, cy = center(b)
    dx, dy = toward[0] - cx, toward[1] - cy
    sx = (b[3] / 2) / abs(dx) if dx else 1e9
    sy = (b[4] / 2) / abs(dy) if dy else 1e9
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def main() -> int:
    by = {b[0]: b for b in BOXES}
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">',
        '<title id="t">AccessCast: what runs where</title>',
        '<desc id="d">A video is analysed on our computer; Gemma 4 31B on AMD Token Factory looks and writes; code plans and '
        "checks every line and sends failures back to Gemma; a person approves; voices and rendering run on our computer; "
        "a render gate refuses while any line waits; viewers pick their version in the player.</desc>",
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#141B34"/></marker></defs>',
        f'<rect width="{W}" height="{H}" fill="#F6F1E7"/>',
        '<text x="40" y="70" font-family="DejaVu Sans, sans-serif" font-size="40" font-weight="bold" fill="#141B34">How AccessCast works: what runs where</text>',
    ]
    for a, b in ARROWS:
        A, B = by[a], by[b]
        p1, p2 = edge(A, center(B)), edge(B, center(A))
        if (a, b) == ("checks", "gemma"):
            p1, p2 = (p1[0] + 60, p1[1]), (p2[0] + 60, p2[1])
        elif (a, b) == ("gemma", "checks"):
            p1, p2 = (p1[0] - 60, p1[1]), (p2[0] - 60, p2[1])
        out.append(
            f'<line x1="{p1[0]:.0f}" y1="{p1[1]:.0f}" x2="{p2[0]:.0f}" y2="{p2[1]:.0f}" stroke="#141B34" stroke-width="3" marker-end="url(#a)"/>'
        )
    for _bid, x, y, w, h, kind, title, lines in BOXES:
        fill, ink = COL[kind]
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{fill}"/>')
        out.append(
            f'<text x="{x + 18}" y="{y + 38}" font-family="DejaVu Sans, sans-serif" font-size="22" font-weight="bold" fill="{ink}">{escape(title)}</text>'
        )
        for i, ln in enumerate(lines):
            out.append(
                f'<text x="{x + 18}" y="{y + 70 + 26 * i}" font-family="DejaVu Sans, Noto Sans Devanagari, sans-serif" font-size="18" fill="{ink}">{escape(ln)}</text>'
            )
    legend = [
        ("amd", "AMD Token Factory"),
        ("pc", "our computer"),
        ("code", "code"),
        ("person", "a person"),
        ("browser", "the viewer's browser"),
    ]
    for i, (k, label) in enumerate(legend):
        x = 40 + i * 300
        out.append(f'<rect x="{x}" y="800" width="34" height="34" rx="8" fill="{COL[k][0]}"/>')
        out.append(
            f'<text x="{x + 46}" y="826" font-family="DejaVu Sans, sans-serif" font-size="22" fill="#141B34">{escape(label)}</text>'
        )
    out.append("</svg>")
    (ROOT / "docs" / "architecture.svg").write_text("\n".join(out), encoding="utf-8")
    print(ROOT / "docs" / "architecture.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

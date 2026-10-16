"""W3C DAPT export (Dubbing and Audio description Profiles of TTML2; Candidate Recommendation Draft, 2026).

One TTML document per script: English description `asRecorded` (the approved, voiced lines with their audio
files), original transcript (`originalTranscript`), and Hindi/Italian translations (`translatedTranscript`).
Each script event is a <div> with begin/end and daptm:represents; the text is in a <p>. Best effort against the
draft spec; validated here for XML well-formedness only, and labelled as such in the docs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from xml.etree import ElementTree as ET

from accesscast.project import atomic_write_text
from accesscast.schemas import Item

TT = "http://www.w3.org/ns/ttml"
TTP = "http://www.w3.org/ns/ttml#parameter"
DAPTM = "http://www.w3.org/ns/ttml/profile/dapt#metadata"
XML = "http://www.w3.org/XML/1998/namespace"
PROFILE = "http://www.w3.org/ns/ttml/profile/dapt1.0/content"
ET.register_namespace("", TT)
ET.register_namespace("ttp", TTP)
ET.register_namespace("daptm", DAPTM)


def _clock(ms: int) -> str:
    return f"{max(0, ms) / 1000:.3f}s"


def build_dapt(
    items: Sequence[Item],
    *,
    script_type: str,
    represents: str,
    lang: str,
    end_of: Callable[[Item], int] | None = None,
) -> str:
    tt = ET.Element(
        f"{{{TT}}}tt",
        {
            f"{{{XML}}}lang": lang,
            f"{{{TTP}}}contentProfiles": PROFILE,
            f"{{{DAPTM}}}scriptType": script_type,
            f"{{{DAPTM}}}scriptRepresents": represents,
            f"{{{TTP}}}timeBase": "media",
        },
    )
    body = ET.SubElement(tt, f"{{{TT}}}body")
    for k, it in enumerate(sorted(items, key=lambda i: i.anchor_ms)):
        begin = it.anchor_ms
        end = end_of(it) if end_of else it.slot.end_ms
        div = ET.SubElement(
            body,
            f"{{{TT}}}div",
            {
                f"{{{XML}}}id": f"e{k + 1}",
                "begin": _clock(begin),
                "end": _clock(max(end, begin + 1)),
                f"{{{DAPTM}}}represents": represents,
            },
        )
        p = ET.SubElement(div, f"{{{TT}}}p", {f"{{{XML}}}lang": it.lang})
        p.text = it.text.replace("\n", " ")
        if it.tts is not None and script_type == "asRecorded":
            ET.SubElement(div, f"{{{TT}}}audio", {"src": f"tts/{it.tts.sha256}.wav"})
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(tt, encoding="unicode")


def export_all(
    out_dir: Path,
    ad_en: Sequence[Item],
    sdh: Sequence[Item],
    subs: dict[str, Sequence[Item]],
    end_of_ad: Callable[[Item], int] | None = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    if ad_en:
        f = out_dir / "description.en.asRecorded.ttml"
        atomic_write_text(
            f,
            build_dapt(
                ad_en, script_type="asRecorded", represents="visual.nonText", lang="en", end_of=end_of_ad
            ),
        )
        files.append(f)
    if sdh:
        f = out_dir / "transcript.en.originalTranscript.ttml"
        atomic_write_text(
            f,
            build_dapt(
                [i for i in sdh if "sound_tag" not in i.flags],
                script_type="originalTranscript",
                represents="audio.dialogue",
                lang="en",
            ),
        )
        files.append(f)
    for lang, items in subs.items():
        if items:
            f = out_dir / f"transcript.{lang}.translatedTranscript.ttml"
            atomic_write_text(
                f,
                build_dapt(items, script_type="translatedTranscript", represents="audio.dialogue", lang=lang),
            )
            files.append(f)
    return files

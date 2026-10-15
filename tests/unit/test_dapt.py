from xml.etree import ElementTree as ET

from accesscast.captions.dapt import DAPTM, TT, build_dapt
from tests.unit.conftest import make_item


def test_dapt_is_well_formed_and_typed():
    xml = build_dapt([make_item("On screen: Ctrl + C."), make_item("A dog opens its mouth.", id="ad.en.0002",
                                                                     anchor_ms=5000)],
                     script_type="asRecorded", represents="visual.nonText", lang="en")
    root = ET.fromstring(xml.split("\n", 1)[1])
    assert root.tag == f"{{{TT}}}tt"
    assert root.get(f"{{{DAPTM}}}scriptType") == "asRecorded"
    divs = root.findall(f".//{{{TT}}}div")
    assert len(divs) == 2 and divs[0].get("begin") == "2.100s"

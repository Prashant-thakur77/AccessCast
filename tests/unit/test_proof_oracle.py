import json

from eval.e11_adversarial import oracle as e11_oracle

from accesscast.config import REPO_ROOT
from accesscast.proof.api import oracle


def test_proof_api_oracle_matches_e11_on_every_case():
    samples = [
        "Press the button 3 times.",
        "Press 3 times in 10 seconds.",
        'On screen: "certified safe".',
        "The product is certified safe.",
        "यह एक test है",
        "A dog barks.",
        "Do not unplug it.",
    ]
    for f in sorted((REPO_ROOT / "data" / "adversarial").glob("*.json")):
        spec = json.loads(f.read_text())
        if spec["oracle"]["type"] == "overlap":
            continue
        for t in samples:
            assert oracle(spec, t) == e11_oracle(spec, t), (f.name, t)

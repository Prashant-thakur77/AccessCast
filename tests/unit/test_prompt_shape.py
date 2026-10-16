from accesscast.llm.promptlib import PROMPT_DIR, load_prompt


def test_every_prompt_sends_its_output_shape():
    for f in sorted(PROMPT_DIR.glob("*.md")):
        p = load_prompt(f.stem)
        if p.schema:
            assert "Output shape" in p.system, f.stem
            for key in p.schema:
                assert f'"{key}"' in p.system, (f.stem, key)

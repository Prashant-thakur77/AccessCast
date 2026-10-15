import pytest

from accesscast.errors import LlmOutputError
from accesscast.llm.json_utils import extract_last_object


def test_extracts_last_object_from_fences():
    assert extract_last_object('noise {"a": 1} more ```json\n{"b": "}"}\n```') == {"b": "}"}


@pytest.mark.parametrize("bad", ["", "[1, 2]", "{not json}", "////////"])
def test_fails_closed(bad):
    with pytest.raises(LlmOutputError):
        extract_last_object(bad)

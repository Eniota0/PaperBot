import json

import httpx
import pytest
import respx

from paperbot.llm import LLMError, LLMUnavailable
from paperbot.llm.ollama import OllamaProvider

URL = "http://localhost:11434/api/chat"
SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}}


def provider():
    return OllamaProvider("http://localhost:11434", "m")


@respx.mock
def test_request_and_parse():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json={"message": {"content": '{"a": "x"}'}}))
    assert provider().complete_json("hello", SCHEMA) == {"a": "x"}
    body = json.loads(route.calls.last.request.content)
    assert body["format"] == SCHEMA and body["stream"] is False and body["model"] == "m"
    assert body["messages"] == [{"role": "user", "content": "hello"}]


@respx.mock
def test_non_json_content_is_llm_error():
    respx.post(URL).mock(return_value=httpx.Response(200, json={"message": {"content": "not json"}}))
    with pytest.raises(LLMError) as e:
        provider().complete_json("p", SCHEMA)
    assert not isinstance(e.value, LLMUnavailable)


@respx.mock
def test_connect_error_is_unavailable():
    respx.post(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(LLMUnavailable, match="Is Ollama running?"):
        provider().complete_json("p", SCHEMA)


@respx.mock
def test_model_not_found_is_unavailable():  # model not pulled -> abort, don't fall back per paper
    respx.post(URL).mock(return_value=httpx.Response(404, json={"error": "model 'm' not found"}))
    with pytest.raises(LLMUnavailable, match="ollama pull m"):
        provider().complete_json("p", SCHEMA)

"""ClaudeExtractor against the real SDK with a fake HTTP transport: no network, no API key needed."""

from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx2
import pytest

from hazar_api.config import Settings
from hazar_api.extraction import FORM_106_FIELDS, ClaudeExtractor, ExtractionError, make_mock_png


def _message(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def _extractor(handler: Any) -> tuple[ClaudeExtractor, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def wrapped(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        response: httpx2.Response = handler(request)
        return response

    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(wrapped)),
    )
    return ClaudeExtractor(Settings(env="test"), client=client), seen


ANSWER = {f.name: {"value": None, "confidence": 0.0} for f in FORM_106_FIELDS} | {
    "tax_year": {"value": "2023", "confidence": 0.97},
    "tax_withheld": {"value": "21340", "confidence": 0.8},
}


async def test_request_shape_and_parsing() -> None:
    extractor, seen = _extractor(lambda _req: httpx2.Response(200, json=_message(json.dumps(ANSWER))))
    result = await extractor.extract(make_mock_png({}), "image/png", "form_106")

    assert result.fields["tax_year"].value == "2023"
    assert result.low_confidence() == [f.name for f in FORM_106_FIELDS if f.name != "tax_year"]

    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]
    assert body["output_config"]["effort"] == "high"
    schema = body["output_config"]["format"]["schema"]
    assert set(schema["properties"]) == {f.name for f in FORM_106_FIELDS}
    image = body["messages"][0]["content"][0]
    assert image["type"] == "image"
    assert image["source"]["media_type"] == "image/png"
    assert "ID numbers" in body["system"]
    assert "temperature" not in body


async def test_pdf_is_sent_as_document() -> None:
    extractor, seen = _extractor(lambda _req: httpx2.Response(200, json=_message(json.dumps(ANSWER))))
    await extractor.extract(b"%PDF-1.7", "application/pdf", "form_106")
    block = json.loads(seen[0].content)["messages"][0]["content"][0]
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx2.Response(200, json=_message("", stop_reason="refusal")), "refused"),
        (httpx2.Response(200, json=_message('{"tax_year": 5}')), "invalid_output"),
        (
            httpx2.Response(
                429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "x"}}
            ),
            "rate_limited",
        ),
        (
            httpx2.Response(
                400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "x"}}
            ),
            "rejected",
        ),
        (
            httpx2.Response(
                529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}
            ),
            "server_error",
        ),
    ],
)
async def test_errors_map_to_codes(response: httpx2.Response, code: str) -> None:
    extractor, _ = _extractor(lambda _req: response)
    with pytest.raises(ExtractionError) as err:
        await extractor.extract(make_mock_png({}), "image/png", "form_106")
    assert err.value.code == code

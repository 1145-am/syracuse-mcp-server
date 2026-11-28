"""Unit tests for relaying x402 payments between MCP tool calls and the backend API."""

import base64
import json

import httpx
import pytest

from util.x402_relay import (
    PAYMENT_META_KEY,
    PAYMENT_RESPONSE_META_KEY,
    error_result,
    payment_headers,
    tool_result,
)

PAYMENT_REQUIRED = {
    "x402Version": 2,
    "error": "Payment required",
    "resource": {"url": "https://api.test/api/v1/stories/"},
    "accepts": [{"scheme": "exact", "network": "eip155:8453", "amount": "10000"}],
}
RECEIPT = {"success": True, "transaction": "0xabc", "network": "eip155:8453", "payer": "0xpayer"}


def _payment(amount, free, free_calls_remaining=None, network="eip155:8453"):
    return {"amount": amount, "currency": "USDC", "network": network, "free": free,
            "free_calls_remaining": free_calls_remaining}


def _b64(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _resp(status=200, body=None, headers=None, text=None):
    if body is not None:
        return httpx.Response(status, json=body, headers=headers)
    return httpx.Response(status, text=text or "", headers=headers)


class TestPaymentHeaders:
    def test_no_meta_sends_no_payment(self):
        assert payment_headers(None) == {}
        assert payment_headers({"progressToken": 1}) == {}

    def test_payment_dict_becomes_base64_signature_header(self):
        payload = {"x402Version": 2, "payload": {"signature": "0xsig"}}
        headers = payment_headers({PAYMENT_META_KEY: payload})
        assert json.loads(base64.b64decode(headers["PAYMENT-SIGNATURE"])) == payload

    def test_payment_json_string_is_accepted(self):
        payload = {"x402Version": 2, "payload": {"signature": "0xsig"}}
        headers = payment_headers({PAYMENT_META_KEY: json.dumps(payload)})
        assert json.loads(base64.b64decode(headers["PAYMENT-SIGNATURE"])) == payload

    def test_malformed_payment_raises(self):
        with pytest.raises(ValueError):
            payment_headers({PAYMENT_META_KEY: "not json"})


class TestToolResult:
    def test_402_with_payment_required_header_becomes_payment_required_result(self):
        resp = _resp(402, body={}, headers={"PAYMENT-REQUIRED": _b64(PAYMENT_REQUIRED)})
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert result.structuredContent == PAYMENT_REQUIRED
        assert json.loads(result.content[0].text) == PAYMENT_REQUIRED

    def test_failed_settlement_receipt_is_carried_in_payment_required_result(self):
        failed = {"success": False, "errorReason": "insufficient_funds", "transaction": "",
                  "network": "eip155:8453"}
        resp = _resp(402, body={}, headers={
            "PAYMENT-REQUIRED": _b64(PAYMENT_REQUIRED), "PAYMENT-RESPONSE": _b64(failed)})
        result = tool_result("stories_list", resp)
        assert result.structuredContent[PAYMENT_RESPONSE_META_KEY] == failed

    def test_402_without_payment_required_header_is_an_ordinary_error(self):
        resp = _resp(402, body={"detail": "Payment settlement failed"})
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert result.structuredContent == {"detail": "Payment settlement failed"}
        assert result.content[0].text == \
            "stories_list failed with HTTP 402 Payment Required: Payment settlement failed"

    def test_other_errors_include_status_and_body(self):
        resp = _resp(400, body={"message": "Must include at least one of org_uri"})
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert "400 Bad Request" in result.content[0].text
        assert "Must include at least one of org_uri" in result.content[0].text
        assert result.structuredContent == {"message": "Must include at least one of org_uri"}

    def test_errors_without_a_json_object_body_have_no_structured_content(self):
        for resp in (_resp(500, text="oops"), _resp(400, body=["bad"])):
            result = tool_result("stories_list", resp)
            assert result.isError is True
            assert result.structuredContent is None

    def test_paid_success_carries_receipt_in_meta(self):
        resp = _resp(200, body={"results": [1]}, headers={"PAYMENT-RESPONSE": _b64(RECEIPT)})
        result = tool_result("stories_list", resp)
        assert not result.isError
        assert result.meta == {PAYMENT_RESPONSE_META_KEY: RECEIPT}
        assert json.loads(result.content[0].text) == {"results": [1]}
        assert result.structuredContent == {"results": [1]}

    def test_paid_call_says_what_it_cost(self):
        body = {"results": [1], "payment": _payment("0.02", free=False)}
        result = tool_result("stories_list", _resp(200, body=body))
        assert json.loads(result.content[0].text) == body
        assert result.structuredContent == body
        assert result.content[1].text == "This call cost 0.02 USDC on Base."

    def test_free_call_says_how_many_free_calls_are_left(self):
        body = {"results": [1], "payment": _payment("0", free=True, free_calls_remaining=49)}
        result = tool_result("stories_list", _resp(200, body=body))
        assert result.content[1].text == "This call was free. Free calls left for this wallet: 49."
        assert result.meta is None

    def test_uncharged_call_says_it_cost_nothing(self):
        body = {"results": [], "payment": _payment("0", free=True)}
        result = tool_result("stories_list", _resp(200, body=body))
        assert result.content[1].text == "This call cost nothing."

    def test_unknown_network_is_named_by_its_id(self):
        body = {"results": [1], "payment": _payment("0.02", free=False, network="eip155:1")}
        result = tool_result("stories_list", _resp(200, body=body))
        assert result.content[1].text == "This call cost 0.02 USDC on eip155:1."

    def test_no_payment_sentence_without_a_payment_object(self):
        for body in ({"results": [1]}, {"results": [1], "payment": None}, [1]):
            result = tool_result("stories_list", _resp(200, body=body))
            assert len(result.content) == 1
            assert json.loads(result.content[0].text) == body

    def test_non_object_json_has_no_structured_content(self):
        result = tool_result("stories_list", _resp(200, body=[1]))
        assert result.structuredContent is None
        assert json.loads(result.content[0].text) == [1]

    def test_unpaid_success_has_no_meta(self):
        result = tool_result("stories_list", _resp(200, body={"results": [1]}))
        assert not result.isError
        assert result.meta is None

    def test_non_json_success_returns_text(self):
        resp = _resp(200, text="plain")
        result = tool_result("stories_list", resp)
        assert result.content[0].text == "Response from stories_list: plain"
        assert result.structuredContent is None


def test_error_result_is_flagged_as_an_error():
    result = error_result("Request to stories_list timed out after 30 seconds")
    assert result.isError is True
    assert result.structuredContent is None
    assert result.content[0].text == "Request to stories_list timed out after 30 seconds"

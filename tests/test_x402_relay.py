"""Unit tests for relaying x402 payments between MCP tool calls and the backend API."""

import base64
import json
import types

import pytest
from requests.structures import CaseInsensitiveDict

from util.x402_relay import (
    FREE_CALLS_REMAINING_META_KEY,
    PAYMENT_META_KEY,
    PAYMENT_RESPONSE_META_KEY,
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


def _b64(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _resp(status=200, body=None, headers=None, reason="OK"):
    text = json.dumps(body) if body is not None else ""

    def _json():
        if body is None:
            raise json.JSONDecodeError("empty", "", 0)
        return body

    return types.SimpleNamespace(
        status_code=status,
        ok=status < 400,
        reason=reason,
        text=text,
        headers=CaseInsensitiveDict(headers or {}),
        json=_json,
    )


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
        resp = _resp(402, body={}, headers={"PAYMENT-REQUIRED": _b64(PAYMENT_REQUIRED)},
                     reason="Payment Required")
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert result.structuredContent == PAYMENT_REQUIRED
        assert json.loads(result.content[0].text) == PAYMENT_REQUIRED

    def test_failed_settlement_receipt_is_carried_in_payment_required_result(self):
        failed = {"success": False, "errorReason": "insufficient_funds", "transaction": "",
                  "network": "eip155:8453"}
        resp = _resp(402, body={}, reason="Payment Required", headers={
            "PAYMENT-REQUIRED": _b64(PAYMENT_REQUIRED), "PAYMENT-RESPONSE": _b64(failed)})
        result = tool_result("stories_list", resp)
        assert result.structuredContent[PAYMENT_RESPONSE_META_KEY] == failed

    def test_402_without_payment_required_header_is_an_ordinary_error(self):
        resp = _resp(402, body={"detail": "Payment settlement failed"}, reason="Payment Required")
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert result.structuredContent is None
        assert "Payment settlement failed" in result.content[0].text

    def test_other_errors_include_status_and_body(self):
        resp = _resp(400, body={"message": "Must include at least one of org_uri"},
                     reason="Bad Request")
        result = tool_result("stories_list", resp)
        assert result.isError is True
        assert "400 Bad Request" in result.content[0].text
        assert "Must include at least one of org_uri" in result.content[0].text

    def test_paid_success_carries_receipt_in_meta(self):
        resp = _resp(200, body={"results": [1]}, headers={"PAYMENT-RESPONSE": _b64(RECEIPT)})
        result = tool_result("stories_list", resp)
        assert not result.isError
        assert result.meta == {PAYMENT_RESPONSE_META_KEY: RECEIPT}
        assert '"results"' in result.content[0].text

    def test_free_call_reports_calls_left_in_meta_and_text(self):
        resp = _resp(200, body={"results": [1]}, headers={"X-Free-Calls-Remaining": "49"})
        result = tool_result("stories_list", resp)
        assert result.meta == {FREE_CALLS_REMAINING_META_KEY: 49}
        assert "This call was free. Free calls left for this wallet: 49." in result.content[0].text

    def test_unpaid_success_has_no_meta(self):
        result = tool_result("stories_list", _resp(200, body={"results": [1]}))
        assert not result.isError
        assert result.meta is None

    def test_non_json_success_returns_text(self):
        resp = _resp(200)
        resp.text = "plain"
        result = tool_result("stories_list", resp)
        assert result.content[0].text == "Response from stories_list: plain"

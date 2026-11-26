"""Relay x402 payments between MCP tool calls and the backend API's HTTP x402 headers.

The backend verifies and settles; this module only translates between the x402 MCP
transport (`_meta` keys, payment-required tool results) and the HTTP headers.
"""

import base64
import json

import mcp.types as types

from util.shared import describe_http_error

PAYMENT_META_KEY = "x402/payment"
PAYMENT_RESPONSE_META_KEY = "x402/payment-response"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"
FREE_CALLS_REMAINING_HEADER = "X-Free-Calls-Remaining"
FREE_CALLS_REMAINING_META_KEY = "syracuse/free-calls-remaining"


def _encode(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _decode(value: str):
    return json.loads(base64.b64decode(value).decode())


def _text(text: str) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=text)]


def payment_headers(meta: dict | None) -> dict:
    payment = (meta or {}).get(PAYMENT_META_KEY)
    if payment is None:
        return {}
    if isinstance(payment, str):
        payment = json.loads(payment)
    return {PAYMENT_SIGNATURE_HEADER: _encode(payment)}


def tool_result(tool_name: str, resp) -> types.CallToolResult:
    receipt_header = resp.headers.get(PAYMENT_RESPONSE_HEADER)
    receipt = _decode(receipt_header) if receipt_header else None

    required_header = resp.headers.get(PAYMENT_REQUIRED_HEADER)
    if resp.status_code == 402 and required_header:
        payment_required = _decode(required_header)
        if receipt is not None:
            payment_required[PAYMENT_RESPONSE_META_KEY] = receipt
        return types.CallToolResult(content=_text(json.dumps(payment_required)),
                                    structuredContent=payment_required, isError=True)

    meta = {PAYMENT_RESPONSE_META_KEY: receipt} if receipt is not None else {}
    free_left = resp.headers.get(FREE_CALLS_REMAINING_HEADER)
    if free_left is not None:
        meta[FREE_CALLS_REMAINING_META_KEY] = int(free_left)
    meta = meta or None
    if not resp.ok:
        return types.CallToolResult(content=_text(describe_http_error(tool_name, resp)),
                                    isError=True, _meta=meta)
    try:
        text = f"Successfully called {tool_name}. Response: {json.dumps(resp.json(), indent=2)}"
        if free_left is not None:
            text += f"\n\nThis call was free. Free calls left for this wallet: {free_left}."
    except json.JSONDecodeError:
        text = f"Response from {tool_name}: {resp.text}"
    return types.CallToolResult(content=_text(text), _meta=meta)

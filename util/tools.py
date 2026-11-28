"""MCP tool listing and execution shared by the stdio and Streamable HTTP servers.

Each server supplies its own auth headers; everything else about turning an MCP
tool call into a backend API request, and the response into a tool result, lives here.
"""

from typing import Any

import mcp.types as types
import requests

from util.log import logger
from util.shared import tool_annotations
from util.vars import API_BASE_URL, OPENAPI_SPEC_URL
from util.x402_relay import error_result, tool_result

REQUEST_TIMEOUT_SECONDS = 30


def list_tools(openapi_spec) -> list[types.Tool]:
    return [
        types.Tool(
            name=tool_info["name"],
            description=tool_info["description"],
            inputSchema=tool_info["inputSchema"],
            annotations=types.ToolAnnotations(**tool_annotations(tool_info)),
            _meta={"requiresAuth": tool_info.get("requires_auth", False)},
        )
        for tool_info in openapi_spec.tools_cache.values()
    ]


def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=OPENAPI_SPEC_URL,
            name="API Schema",
            description="OpenAPI specification for available endpoints",
            mimeType="application/json",
        )
    ]


def read_resource(openapi_spec, uri) -> str:
    logger.info(f"Reading resource: {uri}")
    if str(uri) == OPENAPI_SPEC_URL:
        return openapi_spec.raw_openapi_spec
    raise ValueError(f"Unknown resource URI: {uri}")


def build_url(tool_info: dict[str, Any], arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The request URL, with path parameters filled in, and the remaining arguments."""
    endpoint = tool_info["endpoint"]
    params = dict(arguments)
    for key, value in list(params.items()):
        placeholder = "{" + key + "}"
        if placeholder in endpoint:
            endpoint = endpoint.replace(placeholder, str(value))
            del params[key]
    return API_BASE_URL.rstrip("/") + endpoint, params


def call_tool(openapi_spec, name: str, arguments: dict[str, Any], headers: dict[str, str]) -> types.CallToolResult:
    tool_info = openapi_spec.tools_cache.get(name)
    if tool_info is None:
        return error_result(f"Tool '{name}' not found. Available tools: {list(openapi_spec.tools_cache)}")

    url, params = build_url(tool_info, arguments)
    method = tool_info["method"].upper()
    logger.info(f"Making {method} request to {url}")
    try:
        if method == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        elif method == "POST":
            resp = requests.post(url, json=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        else:
            return error_result(f"Unsupported method: {method}")
    except requests.exceptions.Timeout:
        return _logged_error(f"Request to {name} timed out after {REQUEST_TIMEOUT_SECONDS} seconds")
    except requests.exceptions.RequestException as e:
        return _logged_error(f"API request failed: {e}")
    except Exception as e:
        return _logged_error(f"Error executing tool '{name}': {e}")

    logger.info(f"Tool '{name}' returned HTTP {resp.status_code}")
    return tool_result(name, resp)


def _logged_error(message: str) -> types.CallToolResult:
    logger.error(message)
    return error_result(message)

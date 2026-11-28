"""Unit tests for the tool listing and execution shared by both MCP servers."""

import json
import types

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from util import tools
from util.vars import API_BASE_URL, OPENAPI_SPEC_URL

STORIES_LIST = {
    "name": "stories_list",
    "description": "List stories",
    "endpoint": "/api/v1/stories/",
    "method": "GET",
    "inputSchema": {"type": "object", "properties": {"org_name": {"type": "string"}}, "required": []},
    "requires_auth": True,
    "title": "List stories",
}
STORY_RETRIEVE = {
    "name": "stories_retrieve",
    "description": "One story",
    "endpoint": "/api/v1/stories/{id}/",
    "method": "GET",
    "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    "requires_auth": True,
}
KEY_CREATE = {
    "name": "api_key_create",
    "description": "Create a key",
    "endpoint": "/api/v1/register-and-get-key/",
    "method": "POST",
    "inputSchema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    "requires_auth": False,
}


def _spec(*tool_infos):
    return types.SimpleNamespace(
        tools_cache={t["name"]: t for t in tool_infos},
        raw_openapi_spec='{"openapi": "3.0.3"}',
    )


def _response(status=200, body=None, reason="OK"):
    resp = requests.Response()
    resp.status_code = status
    resp.reason = reason
    resp.headers = CaseInsensitiveDict({"Content-Type": "application/json"})
    resp._content = json.dumps(body).encode() if body is not None else b"plain"
    return resp


@pytest.fixture
def http(monkeypatch):
    """Record outgoing requests and answer them with a canned response."""
    calls = []
    state = types.SimpleNamespace(calls=calls, response=_response(body={"results": []}), raises=None)

    def fake(method):
        def send(url, **kwargs):
            calls.append((method, url, kwargs))
            if state.raises:
                raise state.raises
            return state.response
        return send

    monkeypatch.setattr(tools.requests, "get", fake("GET"))
    monkeypatch.setattr(tools.requests, "post", fake("POST"))
    return state


class TestListTools:
    def test_lists_every_cached_tool(self):
        listed = tools.list_tools(_spec(STORIES_LIST, KEY_CREATE))
        assert [t.name for t in listed] == ["stories_list", "api_key_create"]
        assert listed[0].inputSchema == STORIES_LIST["inputSchema"]
        assert listed[0].annotations.readOnlyHint is True
        assert listed[1].annotations.readOnlyHint is False

    def test_carries_requires_auth_in_meta(self):
        listed = tools.list_tools(_spec(STORIES_LIST, KEY_CREATE))
        assert [t.meta for t in listed] == [{"requiresAuth": True}, {"requiresAuth": False}]


class TestResources:
    def test_lists_the_openapi_spec(self):
        [resource] = tools.list_resources()
        assert str(resource.uri) == OPENAPI_SPEC_URL

    def test_reads_the_openapi_spec(self):
        assert tools.read_resource(_spec(), OPENAPI_SPEC_URL) == '{"openapi": "3.0.3"}'

    def test_unknown_resource_raises(self):
        with pytest.raises(ValueError, match="Unknown resource URI"):
            tools.read_resource(_spec(), "https://elsewhere.test/x")


class TestBuildUrl:
    def test_fills_path_parameters_and_keeps_the_rest(self):
        url, params = tools.build_url(STORY_RETRIEVE, {"id": "abc", "output": "full"})
        assert url == f"{API_BASE_URL}/api/v1/stories/abc/"
        assert params == {"output": "full"}

    def test_does_not_change_the_callers_arguments(self):
        arguments = {"id": "abc"}
        tools.build_url(STORY_RETRIEVE, arguments)
        assert arguments == {"id": "abc"}


class TestCallTool:
    def test_get_sends_arguments_as_query_params(self, http):
        result = tools.call_tool(_spec(STORIES_LIST), "stories_list", {"org_name": "Coupa"}, {"X-API-Key": "k"})
        [(method, url, kwargs)] = http.calls
        assert method == "GET"
        assert url == f"{API_BASE_URL}/api/v1/stories/"
        assert kwargs["params"] == {"org_name": "Coupa"}
        assert kwargs["headers"] == {"X-API-Key": "k"}
        assert not result.isError
        assert result.structuredContent == {"results": []}

    def test_post_sends_arguments_as_json(self, http):
        tools.call_tool(_spec(KEY_CREATE), "api_key_create", {"email": "a@b.test"}, {})
        [(method, _, kwargs)] = http.calls
        assert method == "POST"
        assert kwargs["json"] == {"email": "a@b.test"}

    def test_unknown_tool_is_an_error(self, http):
        result = tools.call_tool(_spec(STORIES_LIST), "nope", {}, {})
        assert result.isError is True
        assert "Tool 'nope' not found" in result.content[0].text
        assert http.calls == []

    def test_unsupported_method_is_an_error(self, http):
        delete = dict(STORIES_LIST, method="DELETE")
        result = tools.call_tool(_spec(delete), "stories_list", {}, {})
        assert result.isError is True
        assert result.content[0].text == "Unsupported method: DELETE"

    def test_http_error_is_an_error(self, http):
        http.response = _response(400, body={"detail": "bad"}, reason="Bad Request")
        result = tools.call_tool(_spec(STORIES_LIST), "stories_list", {}, {})
        assert result.isError is True
        assert "HTTP 400 Bad Request" in result.content[0].text

    @pytest.mark.parametrize("exc, message", [
        (requests.exceptions.Timeout(), "Request to stories_list timed out after 30 seconds"),
        (requests.exceptions.ConnectionError("refused"), "API request failed: refused"),
        (RuntimeError("boom"), "Error executing tool 'stories_list': boom"),
    ])
    def test_request_failures_are_errors(self, http, exc, message):
        http.raises = exc
        result = tools.call_tool(_spec(STORIES_LIST), "stories_list", {}, {})
        assert result.isError is True
        assert result.content[0].text == message

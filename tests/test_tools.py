"""Unit tests for the tool listing and execution shared by both MCP servers."""

import asyncio
import json
import types

import httpx
import pytest

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


@pytest.fixture
def http(monkeypatch):
    """Record outgoing requests and answer them with a canned response."""
    state = types.SimpleNamespace(requests=[], response=httpx.Response(200, json={"results": []}), raises=None)

    def handler(request: httpx.Request) -> httpx.Response:
        state.requests.append(request)
        if state.raises:
            raise state.raises
        return state.response

    monkeypatch.setattr(tools, "_transport", httpx.MockTransport(handler))
    return state


def _call(spec, name, arguments, headers=None):
    return asyncio.run(tools.call_tool(spec, name, arguments, headers or {}))


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
        result = _call(_spec(STORIES_LIST), "stories_list", {"org_name": "Coupa"}, {"X-API-Key": "k"})
        [request] = http.requests
        assert request.method == "GET"
        assert str(request.url) == f"{API_BASE_URL}/api/v1/stories/?org_name=Coupa"
        assert request.headers["X-API-Key"] == "k"
        assert not result.isError
        assert result.structuredContent == {"results": []}

    def test_get_repeats_list_params_and_drops_none(self, http):
        _call(_spec(STORIES_LIST), "stories_list", {"type": ["a", "b"], "org_name": None})
        [request] = http.requests
        assert request.url.query == b"type=a&type=b"

    def test_post_sends_arguments_as_json(self, http):
        _call(_spec(KEY_CREATE), "api_key_create", {"email": "a@b.test"})
        [request] = http.requests
        assert request.method == "POST"
        assert json.loads(request.content) == {"email": "a@b.test"}

    def test_unknown_tool_is_an_error(self, http):
        result = _call(_spec(STORIES_LIST), "nope", {})
        assert result.isError is True
        assert "Tool 'nope' not found" in result.content[0].text
        assert http.requests == []

    def test_unsupported_method_is_an_error(self, http):
        delete = dict(STORIES_LIST, method="DELETE")
        result = _call(_spec(delete), "stories_list", {})
        assert result.isError is True
        assert result.content[0].text == "Unsupported method: DELETE"
        assert http.requests == []

    def test_http_error_is_an_error(self, http):
        http.response = httpx.Response(400, json={"detail": "bad"})
        result = _call(_spec(STORIES_LIST), "stories_list", {})
        assert result.isError is True
        assert "HTTP 400 Bad Request" in result.content[0].text

    @pytest.mark.parametrize("exc, message", [
        (httpx.ReadTimeout("slow"), "Request to stories_list timed out after 30 seconds"),
        (httpx.ConnectError("refused"), "API request failed: refused"),
        (RuntimeError("boom"), "Error executing tool 'stories_list': boom"),
    ])
    def test_request_failures_are_errors(self, http, exc, message):
        http.raises = exc
        result = _call(_spec(STORIES_LIST), "stories_list", {})
        assert result.isError is True
        assert result.content[0].text == message

    def test_calls_run_concurrently(self, monkeypatch):
        """A slow API call must not hold up other calls on the same event loop."""
        started = []

        async def handler(request: httpx.Request) -> httpx.Response:
            started.append(request.url.params["org_name"])
            await asyncio.sleep(0.2)
            return httpx.Response(200, json={"results": []})

        class AsyncMock(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                return await handler(request)

        monkeypatch.setattr(tools, "_transport", AsyncMock())
        spec = _spec(STORIES_LIST)

        async def both():
            loop = asyncio.get_running_loop()
            t0 = loop.time()
            await asyncio.gather(
                tools.call_tool(spec, "stories_list", {"org_name": "a"}, {}),
                tools.call_tool(spec, "stories_list", {"org_name": "b"}, {}),
            )
            return loop.time() - t0

        elapsed = asyncio.run(both())
        assert sorted(started) == ["a", "b"]
        assert elapsed < 0.35

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, Prompt, Resource, Tool

from util import tools
from util.log import logger
from util.shared import OpenAPISpec
from util.vars import AUTH_HEADER, MCP_SERVER_NAME
from util.x402_relay import payment_headers

openapi_spec = OpenAPISpec()

server = Server(MCP_SERVER_NAME, version=openapi_spec.version)
logger.info("Loaded openapi spec")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return tools.list_tools(openapi_spec)


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return []


@server.list_resources()
async def list_resources() -> list[Resource]:
    return tools.list_resources()


@server.read_resource()
async def read_resource(uri: str) -> str:
    return tools.read_resource(openapi_spec, uri)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    logger.info(f"Calling tool '{name}' with arguments: {arguments}")
    meta = server.request_context.meta.model_extra if server.request_context.meta else None
    headers = {"Content-Type": "application/json"} | AUTH_HEADER | payment_headers(meta)
    return await tools.call_tool(openapi_spec, name, arguments, headers)


async def main():
    logger.info("MCP server ready and waiting for connections...")
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Connected to client via stdio")
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Defaults point at the public Syracuse API. Override at runtime as needed.
# MCP_SERVER_API_TOKEN is optional: tools can be listed and an API key
# registered without one; fetching stories needs a key.
ENV API_BASE_URL=https://syracuse.1145.am \
    OPENAPI_JSON=.well-known/openapi.json \
    AUTH_HEADER_NAME=Authorization \
    API_TOKEN_PREFIX=Token \
    MCP_SERVER_NAME="Syracuse Company News API" \
    MCP_SERVER_DESCRIPTION="Structured company and industry news for AI agents: typed, dated, source-linked events." \
    ALLOWED_TOOLS=register_and_get_key_create,location_groups_list,stories_industry_location_list,stories_organization_list \
    PYTHONUNBUFFERED=1

# stdio transport (for MCP clients / Glama inspection).
# For the HTTP server use: uv run --no-sync stateless_streaming_http_mcp_server.py
CMD ["uv", "run", "--no-sync", "stdio_mcp_server.py"]

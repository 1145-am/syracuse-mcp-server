FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Settings default to the public Syracuse API (see util/vars.py).
# MCP_SERVER_API_TOKEN is optional: tools can be listed and an API key
# registered without one; fetching stories needs a key.
ENV PYTHONUNBUFFERED=1

# stdio transport (for MCP clients / Glama inspection).
# For the HTTP server use: uv run --no-sync stateless_streaming_http_mcp_server.py
CMD ["uv", "run", "--no-sync", "stdio_mcp_server.py"]

# Syracuse Company News MCP Server

An MCP server for the [Syracuse](https://syracuse.1145.am) company news API. Its tools are generated from the API's OpenAPI spec when the server starts.

## API Key

Get a free API key from syracuse.1145.am - all you need to provide is your email address. Here is a curl command to do so:

```
curl -X POST "https://syracuse.1145.am/api/v1/register-and-get-key/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"your_email@example.com\"}"
```

You'll get a low usage level until you confirm the key, so make sure to use an email address that you have access to.

## Using the MCP Server

There are 3 options:

1. Run as a Local MCP Server (e.g. to connect with Claude Desktop)
2. Connect via the Syracuse MCP server
3. Run your own Remote MCP Server locally

### To run as Local MCP Server

Pre-req: Install `uv` 

1. Clone this repo
2. Copy `.env.sample` to `.env` and configure your MCP_SERVER_API_TOKEN with the API key you got above
3. Example claude_desktop_config.json

```
{
  "mcpServers": {
    "Syracuse Company News API": {
      "command": "/path/to/uv",
      "args": [
        "--directory",
        "/path/to/repo/syracuse-mcp-server",
        "run",
        "stdio_mcp_server.py"
      ]
    }
  }
}
```

### To connect via Syracuse's MCP Server

There are no special pre-requisites

Connect to `https://syracuse.1145.am/mcp`. You can connect, register and list location groups without a key. To fetch stories, send your key either as `Authorization: Bearer <key>` or as `X-API-Key: <key>`. A stories call made without a key returns the API's error message (see [API Key](#api-key) above to get one).

MCP doc is at `https://syracuse.1145.am/.well-known/mcp.json`

### Running your own Remote MCP Server

If, for some reason, you want to run your own local MCP server then that is also possible. Again, it expects `uv`.

You don't need to update your key in the `.env` file, but you do need to: 

1. Clone this repo
2. Copy `.env.sample` to `.env` - though any further configuration is not needed
3. Run it with `uv run stateless_streaming_http_mcp_server.py`

The server reads the OpenAPI spec once at startup, so restart it to pick up API changes.

Connection info for MCP Inspector:
- **Transport Type**: Streamable HTTP
- **URL**: host:port/mcp, e.g. `http://127.0.0.1:9000/mcp`
- Anyone making calls that require authorization will need to add their API key in the Authentication section

The Stateless Streaming MCP Server also serves an mcp.json at `.well-known/mcp.json` (in this example it would be `http://127.0.0.1/.well-known/mcp.json` )

## Allowed tools

By default the ALLOWED_TOOLS restricts the MCP server to the minimum needed to register accounts and get stories:
- register_and_get_key_create
- location_groups_list
- stories_industry_location_list
- stories_organization_list

There's no problem to allow all tools - if you'd like to experiment simply remove ALLOWED_TOOLS from `.env`

If a name in ALLOWED_TOOLS isn't in the OpenAPI spec (for example, after an endpoint is renamed), the server refuses to start and names the missing tool.

## Distinguishing tools that need auth

Each tool is tagged with whether it requires authentication, derived from the OpenAPI `security` rules: an operation's `security` overrides the spec-level `security`, and either an empty list (`security: []`) or an empty `{}` entry in the list (auth optional) means the tool doesn't need auth. This is exposed two ways:

- In `tools/list`, each tool carries `_meta: { "requiresAuth": true | false }`.
- In `.well-known/mcp.json`, the same `_meta` flag is present, and the `security` block is only attached to tools that actually require auth.

Clients can use this to call public endpoints without prompting the user for a token, and only request credentials for tools that need them.


# Syracuse Company New MCP Server

Installation notes

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

Connect to `https://syracuse.1145.am/mcp` and provide your key as part of the authorization 

MCP doc is at `https://syracuse.1145.am/.well-known/mcp.json`

### Running your own Remote MCP Server

If, for some reason, you want to run your own local MCP server then that is also possible. Again, it expects `uv`.

You don't need to update your key in the `.env` file, but you do need to: 

1. Clone this repo
2. Copy `.env.sample` to `.env` - though any further configuration is not needed
3. Run it with `uv run http_mcp_server.py`

The Stateless Streaming MCP Server also serves an mcp.json at `.well-known/mcp.json` (in this example it would be `http://127.0.0.1:9000/.well-known/mcp.json` )
By default you'll need to connect to `http://127.0.0.1:9000/mcp`

## Allowed tools

By default the ALLOWED_TOOLS restricts the MCP server to the minimum needed to register accounts and get stories:
- register_and_get_key 
- location_groups_list
- stories

There's no problem to allow all tools - if you'd like to experiment simply remove ALLOWED_TOOLS.




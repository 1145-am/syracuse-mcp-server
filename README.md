# Syracuse Company News MCP Server

[![Glama](https://glama.ai/mcp/servers/1145-am/syracuse-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/1145-am/syracuse-mcp-server)
[![mcptry](https://mcptry.com/badge/io.github.1145-am/syracuse-mcp-server)](https://mcptry.com/servers/io.github.1145-am/syracuse-mcp-server)

Structured company and industry news for AI agents. [Syracuse](https://syracuse.1145.am) turns news into typed, dated, source-linked events, so an agent can use them without a person first weeding out false positives. Events include M&A and investments, partnerships, senior hires and departures, product launches, new or closed locations, financial results, legal and regulatory actions, and incidents.

We do everything we can to avoid false positives: if Syracuse isn't confident a story is really about what you asked for, it leaves it out. So **a call that returns no stories is free**, whether you use an API key or pay per call.

Use the hosted endpoint at `https://syracuse.1145.am/mcp/`. You can pay with a free API key or per call over [x402](https://www.x402.org/), with no account. Either way, the data is covered by the [Terms of Use](https://syracuse.1145.am/terms): it's for your own use, not for resale or redistribution.

## Tools

| Tool | What it does | Needs payment? |
|---|---|---|
| `stories_organization_list` | News about a named company (partial match). Can be narrowed by where the company is based, its industry, where the event happened, story type and recency. | Yes |
| `stories_industry_location_list` | News for an industry and/or the location where events happened (e.g. "biotech" in "texas"). Can be narrowed by story type and recency. | Yes |
| `stories_retrieve` | One story in full, by the `uri` from a stories result. | Yes |
| `location_groups_list` | Valid location names and ids (UN regions, US Census regions, US states, and the states or provinces of some other countries) for the location filters. | No |
| `industry_clusters_list` | Searches industry clusters and returns the ids for the `industry_id` filter. | No |
| `api_key_create` | Creates an account for an email address and returns an API key. The user must accept the Terms of Use. | No |

### Example

`stories_organization_list` with `org_name: "Microsoft"` returns stories like this (extract shortened):

```json
{
  "count": 415,
  "results": [
    {
      "activity_class": "IncidentActivity",
      "label": "widespread outage across Outlook, Teams, and its Copilot AI assistant",
      "headline": "Microsoft says latent July bug triggered global Microsoft 365 outage",
      "document_extract": "Microsoft Corporation (NASDAQ: MSFT) disclosed that a latent software defect lurking in its data centers since July triggered last week's widespread outage across Outlook, Teams, and its Copilot AI assistant...",
      "published_date": "2026-11-16T20:00:48Z",
      "published_by": "Investing.com",
      "document_url": "https://www.investing.com/news/stock-market-news/microsoft-says-latent-july-bug-triggered-global-microsoft-365-outage-5030785",
      "matched_organizations": [
        {"name": "Microsoft Corporation", "role": "organization", "uri": "https://1145.am/db/24398699/Microsoft_Corporation"}
      ]
    }
  ]
}
```

Each story has an event type (`activity_class`), a date, the source publication and a link to the original article. Results are paginated. Pass `output: "full"` for more detail.

All tools carry MCP annotations (`readOnlyHint`, `idempotentHint` and so on). Each tool also carries `_meta.requiresAuth`, so a client knows which tools it can call without credentials.

## How it compares

We benchmark Syracuse against other news search APIs (Exa, Linkup, Perplexity and, until September 2026, Tavily) on the same company and industry queries every few weeks. An AI judge scores the results without knowing which provider is which. It scores precision, coverage, dates and publishers, story quality and trust. The method, the raw results and the full history are in [news-comparison](https://github.com/alanbuxton/news-comparison).

## Connect to the hosted server

Add `https://syracuse.1145.am/mcp/` to your MCP client as a Streamable HTTP server. In Claude Code, for example:

```
claude mcp add --transport http syracuse https://syracuse.1145.am/mcp/ --header "X-API-Key: <your key>"
```

You can connect, list tools, look up location groups and industry clusters, and register for a key without credentials. To fetch stories, either send an API key or pay per call.

The discovery document is at `https://syracuse.1145.am/.well-known/mcp.json`.

### Option 1: API key (free)

Get a key by calling the `api_key_create` tool, or with curl. Registering means accepting the [Terms of Use](https://syracuse.1145.am/terms), so the request must include `"accept_terms": true`:

```
curl -X POST "https://syracuse.1145.am/api/v1/register-and-get-key/" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","accept_terms":true}'
```

A key allows 30 queries a month until you click the link in the verification email, then 300 a month. Only calls that return stories count: empty results and errors don't use up your quota. Contact us (see the website footer) if you need more.

Send the key as `X-API-Key: <key>` or `Authorization: Bearer <key>`.

### Option 2: x402 pay-per-call (no account)

If you send no API key, the stories tools take payment over [x402](https://www.x402.org/): **$0.02 in USDC per call, on Base**. You're only charged when a call returns results. Errors and empty results are free. The 402 response always has the current price and network, so check it if this page is out of date.

**Free calls, 30 November to 7 December 2026:** we're giving away 10,000 free calls, with up to 50 per wallet, until they run out. You sign the payment as usual and it's never settled. Your wallet must still hold at least one call's price in USDC on Base, because the payment is verified, but that balance is never touched. A free call's result says how many free calls your wallet has left, and carries the number in `_meta["syracuse/free-calls-remaining"]`. Details: [syracuse.1145.am/mcptry](https://syracuse.1145.am/mcptry). Paying, including with a free call, means you accept the [Terms of Use](https://syracuse.1145.am/terms).

The server follows the x402 MCP transport:

1. Call a stories tool with no payment. The result has `isError: true`, and its `structuredContent` holds the x402 `PaymentRequired` object (price, network, asset, `payTo`).
2. Sign a payment that matches one of the `accepts` entries. Repeat the call with the payment payload in the request's `_meta["x402/payment"]`.
3. A successful result carries the settlement receipt in `_meta["x402/payment-response"]`.

The server passes payments through to the Syracuse API, which verifies and settles them. Any x402-aware MCP client or agent wallet can handle these steps automatically. In Python, the official `x402` SDK does it (`pip install "x402[evm,mcp]" mcp`):

```python
import asyncio
from eth_account import Account
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from x402 import x402Client
from x402.mcp import x402MCPSession
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.evm.signers import EthAccountSigner


async def main():
    wallet = Account.from_key(PRIVATE_KEY)
    payer = x402Client().register("eip155:*", ExactEvmScheme(signer=EthAccountSigner(wallet)))
    async with streamablehttp_client("https://syracuse.1145.am/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            syracuse = x402MCPSession(session, payer)
            await syracuse.initialize()
            result = await syracuse.call_tool("stories_organization_list", {"org_name": "microsoft"})
            print(result.content[0].text)

asyncio.run(main())
```

## Run it locally

You only need to run your own copy to use the stdio transport (e.g. Claude Desktop with a local process) or to work on the server. The local stdio server always uses the API key from its config, so x402 isn't available in this mode.

### Docker

```
docker build -t syracuse-mcp-server .
docker run -i --rm -e MCP_SERVER_API_TOKEN=<your key> syracuse-mcp-server
```

### uv

Requires [uv](https://docs.astral.sh/uv/).

1. Clone this repo.
2. Copy `.env.sample` to `.env` and set `MCP_SERVER_API_TOKEN` to your API key.
3. Point your client at it. Here's an example `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "Syracuse Company News API": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/syracuse-mcp-server", "run", "stdio_mcp_server.py"]
    }
  }
}
```

### Self-hosting the HTTP server

`uv run stateless_streaming_http_mcp_server.py` starts the same server as the hosted endpoint, at `http://127.0.0.1:9000/mcp` by default. It passes each caller's API key, or x402 payment, through to the API, so it doesn't need a key of its own. It also serves `/.well-known/mcp.json`.

## How it works

The server is a thin layer in front of the Syracuse REST API. At startup it reads the API's OpenAPI spec (`API_BASE_URL` + `OPENAPI_JSON`) and turns each operation into an MCP tool. Tool descriptions, parameters and auth requirements all come from that spec. Restart the server to pick up API changes.

- **`ALLOWED_TOOLS`** limits the server to the six tools above by default. Set it to an empty string (`ALLOWED_TOOLS=`) to expose every API operation. If a listed name isn't in the spec, the server refuses to start and names the missing tool.
- **`requiresAuth`** is worked out from the OpenAPI `security` rules. An operation's own `security` overrides the spec-wide one. Either `security: []` or an empty `{}` entry counts as no auth needed.

### Configuration

All settings are environment variables, usually set in `.env`. They all have defaults that work with the public API, so `.env` is only needed to change them or to set your API key. See [.env.sample](.env.sample).

| Variable | Purpose |
|---|---|
| `API_BASE_URL` | Base URL of the Syracuse API (`https://syracuse.1145.am`). |
| `OPENAPI_JSON` | Path to the OpenAPI spec, relative to `API_BASE_URL`. |
| `MCP_SERVER_API_TOKEN` | Your API key. The stdio server uses it for every call. The HTTP server only uses it to fetch the spec. |
| `AUTH_HEADER_NAME` / `API_TOKEN_PREFIX` | How the key is sent to the API. The server rewrites `Bearer <key>` into the form the API expects (`Token <key>`). |
| `ALLOWED_TOOLS` | Comma-separated list of tool names to expose. |
| `HTTP_MCP_SERVER_PORT` | Port for the HTTP server (default 9000). |
| `MCP_SERVER_NAME` / `MCP_SERVER_DESCRIPTION` | Server name and description reported to clients. |

### Tests

```
uv run pytest
```

## License

The code in this repo is [MIT](LICENSE). The data the server returns comes from the Syracuse API and is covered by the [Terms of Use](https://syracuse.1145.am/terms), not by the MIT licence. Open projects can ask for the data under the [Open Database License](https://opendatacommons.org/licenses/odbl/1-0/): email info-syracuse@1145.am.

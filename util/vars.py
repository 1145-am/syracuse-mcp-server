from dotenv import load_dotenv
import os

# --- Environment ---
# Defaults target the public Syracuse API, so the server runs with no .env.
# Set ALLOWED_TOOLS to an empty string to expose every API operation.
DEFAULT_ALLOWED_TOOLS = "register_and_get_key_create,location_groups_list,stories_industry_location_list,stories_organization_list"
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "https://syracuse.1145.am")
OPENAPI_JSON = os.getenv("OPENAPI_JSON", ".well-known/openapi.json")
OPENAPI_SPEC_URL = f"{API_BASE_URL}/{OPENAPI_JSON}"

MCP_SERVER_API_TOKEN = os.getenv("MCP_SERVER_API_TOKEN", "")
API_TOKEN_PREFIX = os.getenv("API_TOKEN_PREFIX", "Token")
AUTH_HEADER_NAME = os.getenv("AUTH_HEADER_NAME", "Authorization")
AUTH_HEADER = {AUTH_HEADER_NAME: f"{API_TOKEN_PREFIX} {MCP_SERVER_API_TOKEN}".strip()}

MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Syracuse Company News API")
MCP_SERVER_DESCRIPTION = os.getenv("MCP_SERVER_DESCRIPTION", "Structured company and industry news for AI agents: typed, dated, source-linked events.")
HTTP_MCP_SERVER_PORT = int(os.getenv("HTTP_MCP_SERVER_PORT", "9000"))
ALLOWED_TOOLS = [x.strip() for x in os.getenv("ALLOWED_TOOLS", DEFAULT_ALLOWED_TOOLS).split(",") if x.strip()]
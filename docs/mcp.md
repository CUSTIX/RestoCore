# RestoCore MCP server

The [Model Context Protocol](https://modelcontextprotocol.io) lets an AI assistant (for example
Claude Desktop) call *tools* that you provide. RestoCore ships a small MCP server with **read-only**
tools, so an assistant can answer questions like "what's low in stock?" or "how were sales
yesterday?" without being able to change anything.

## How it fits together

```
AI client (Claude Desktop, etc.)
   │  stdio (the client starts the server as a child process)
   ▼
mcp_server/server.py   ── 5 read-only tools
   │  HTTPS/HTTP GET + Authorization: Bearer <token>
   ▼
Django /api/...        ── token check, GET only, reads through each app's selectors
```

Why go through an HTTP API instead of importing Django models directly?

- **Least privilege.** The server can only call GET endpoints. Even a misbehaving tool cannot write.
- **Separation.** The MCP server has its own tiny dependency set (`mcp_server/requirements.txt`)
  and does not need database credentials.
- **One rule set.** The API uses the same selectors as the web pages, so numbers always match.

## Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_bookings` | `date` (YYYY-MM-DD, optional; default today) | bookings for that day |
| `get_low_stock` | — | items at or below reorder level |
| `get_sales_summary` | `date` (optional) | revenue, orders, average, voids, top items |
| `get_menu` | — | public menu |
| `get_staff_on_shift` | — | employees clocked in now |

## Run it locally

1. In `.env`, set a token (the example file already has one for local use):
   `RESTOCORE_API_TOKEN=local-dev-api-token`. Leave it empty to switch the API off (it returns 503).
2. Start RestoCore: `docker compose up`.
3. Install the server's requirements (Python 3.10+ on your machine, ideally in a virtualenv):

   ```bash
   pip install -r mcp_server/requirements.txt
   ```

4. Point your MCP client at it. Example for Claude Desktop (`claude_desktop_config.json`):

   ```json
   {
     "mcpServers": {
       "restocore": {
         "command": "python",
         "args": ["-m", "mcp_server.server"],
         "cwd": "/path/to/restocore",
         "env": {
           "RESTOCORE_API_URL": "http://127.0.0.1:8000",
           "RESTOCORE_API_TOKEN": "local-dev-api-token"
         }
       }
     }
   }
   ```

## Try the API directly

```bash
curl -H "Authorization: Bearer local-dev-api-token" http://127.0.0.1:8000/api/inventory/low-stock/
```

## Tests

`mcp_server/tests/` runs the client against the real Django API views (no network), and
`api/tests/` covers auth (disabled / wrong token / right token), read-only enforcement and date
validation. The MCP server itself was also exercised end to end with `mcp==2.2.0` against a running
instance: all five tools are listed and return data.

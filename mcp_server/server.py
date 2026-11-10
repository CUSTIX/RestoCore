"""RestoCore MCP server: read-only tools over the RestoCore API (stdio transport).

Run:  pip install -r mcp_server/requirements.txt
      RESTOCORE_API_TOKEN=... python -m mcp_server.server
Every tool only reads. Nothing here can change RestoCore data.
"""

from mcp.server.mcpserver import MCPServer

from mcp_server.client import RestoCoreClient

server = MCPServer("restocore")
client = RestoCoreClient()


@server.tool()
def get_bookings(date: str | None = None) -> dict:
    """List table bookings for a day (YYYY-MM-DD). Defaults to today (restaurant time zone)."""
    return client.bookings(date)


@server.tool()
def get_low_stock() -> dict:
    """List inventory items at or below their reorder level."""
    return client.low_stock()


@server.tool()
def get_sales_summary(date: str | None = None) -> dict:
    """Revenue, order count, average order and top items for a day (YYYY-MM-DD, default today)."""
    return client.sales_summary(date)


@server.tool()
def get_menu() -> dict:
    """The public menu: categories, items, prices and descriptions."""
    return client.menu()


@server.tool()
def get_staff_on_shift() -> dict:
    """Employees who are clocked in right now."""
    return client.on_shift()


if __name__ == "__main__":
    server.run()  # stdio

"""Command entry point for the memory MCP server."""

from __future__ import annotations

from memory_mcp.mcp_tools.server import run


def main() -> None:
    """Run the MCP server."""

    run()


if __name__ == "__main__":
    main()

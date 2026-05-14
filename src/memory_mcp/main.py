"""Command entry point for the memory MCP server."""

from __future__ import annotations

import argparse

from memory_mcp.mcp_tools.server import run


def main() -> None:
    parser = argparse.ArgumentParser(description="memory-mcp MCP server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

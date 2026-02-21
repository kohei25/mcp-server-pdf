import asyncio

from mcp.server.stdio import stdio_server

from mcp_server_pdf.server import server


async def main():
    """メイン関数 - MCPサーバーを起動"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main_sync():
    """uvx用の同期エントリーポイント"""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())

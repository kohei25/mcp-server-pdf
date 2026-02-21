from mcp.server import Server
from mcp.types import Tool, TextContent

from mcp_server_pdf.tools.convert import pdf_to_markdown_tool
from mcp_server_pdf.tools.download import download_pdf_tool

server = Server("pdf-processor")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="download_pdf",
            description="PDFのURLからPDFファイルをダウンロードして保存します。保存先はdownload_dirで指定できます。未指定の場合はカレントディレクトリに保存されます。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "ダウンロードするPDFのURL",
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存するファイル名（オプション）。指定しない場合はURLから自動生成されます",
                    },
                    "download_dir": {
                        "type": "string",
                        "description": "PDFを保存するディレクトリのパス（オプション）。指定しない場合はカレントディレクトリに保存されます",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="pdf_to_markdown",
            description="PDFファイルをマークダウン形式に変換します。PyMuPDF4LLMを使用してテキスト、表、画像を含む高品質な変換を行います。",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "変換するPDFファイルのパス",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "出力するマークダウンファイルのパス（オプション）。指定しない場合はPDFと同じディレクトリに.mdファイルを作成",
                    },
                    "pages": {
                        "type": "string",
                        "description": "変換するページ範囲（1始まり。例: '1-5', '1,3,5', 'all'）。デフォルトは'all'",
                    },
                    "extract_images": {
                        "type": "boolean",
                        "description": "画像を抽出するかどうか。デフォルトはtrue",
                    },
                },
                "required": ["pdf_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """ツールの実行"""
    if name == "download_pdf":
        return await download_pdf_tool(arguments)
    elif name == "pdf_to_markdown":
        return await pdf_to_markdown_tool(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

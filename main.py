import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
import aiofiles
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# グローバル設定
CONFIG = {
    "download_base_dir": None,
    "allowed_subdirs": True,  # サブディレクトリの作成を許可するか
}


def load_config(config_path: str = None):
    """設定ファイルまたは環境変数から設定を読み込む"""
    global CONFIG
    
    # 環境変数から読み込み（最優先）
    env_download_dir = os.getenv("PDF_DOWNLOAD_DIR")
    if env_download_dir:
        CONFIG["download_base_dir"] = env_download_dir
        print(f"環境変数からダウンロードディレクトリを設定: {env_download_dir}", file=sys.stderr)
    
    # 設定ファイルから読み込み
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # 環境変数が設定されていない場合のみファイルの設定を使用
                if not env_download_dir:
                    CONFIG.update(file_config)
                else:
                    # download_base_dir以外の設定は更新
                    for key, value in file_config.items():
                        if key != "download_base_dir":
                            CONFIG[key] = value
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}", file=sys.stderr)
    
    # コマンドライン引数から設定を読み込む（環境変数が設定されていない場合のみ）
    if not env_download_dir and len(sys.argv) > 1:
        download_dir = sys.argv[1]
        if Path(download_dir).exists():
            CONFIG["download_base_dir"] = download_dir
        else:
            print(f"指定されたディレクトリが存在しません: {download_dir}", file=sys.stderr)


# MCPサーバーのインスタンスを作成
server = Server("pdf-downloader")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="download_pdf",
            description="PDFのURLからPDFファイルをダウンロードして保存します。設定されたベースディレクトリ以下に保存されます。",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "ダウンロードするPDFのURL"
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存するファイル名（オプション）。指定しない場合はURLから自動生成されます"
                    },
                    "subdir": {
                        "type": "string",
                        "description": "ベースディレクトリ以下のサブディレクトリ名（オプション）"
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="get_download_config",
            description="現在のダウンロード設定を確認します",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """ツールの実行"""
    if name == "download_pdf":
        return await download_pdf_tool(arguments)
    elif name == "get_download_config":
        return await get_download_config_tool()
    else:
        raise ValueError(f"Unknown tool: {name}")


async def get_download_config_tool() -> list[TextContent]:
    """現在のダウンロード設定を返す"""
    base_dir = CONFIG.get("download_base_dir")
    env_dir = os.getenv("PDF_DOWNLOAD_DIR")
    
    config_text = "ダウンロード設定:\n"
    
    if base_dir:
        base_dir_path = Path(base_dir)
        config_text += f"ベースディレクトリ: {base_dir_path.absolute()}\n"
        config_text += f"設定元: {'環境変数 (PDF_DOWNLOAD_DIR)' if env_dir else 'コマンドライン引数または設定ファイル'}\n"
        config_text += f"ディレクトリ存在確認: {'存在' if base_dir_path.exists() else '存在しない'}\n"
    else:
        config_text += "ベースディレクトリ: 未設定（一時ディレクトリを使用）\n"
    
    config_text += f"サブディレクトリ作成: {'許可' if CONFIG.get('allowed_subdirs') else '禁止'}"
    
    return [TextContent(type="text", text=config_text)]


async def download_pdf_tool(arguments: dict) -> list[TextContent]:
    """PDFダウンロードツールの実装"""
    url = arguments.get("url")
    filename = arguments.get("filename")
    subdir = arguments.get("subdir")
    
    if not url:
        return [TextContent(type="text", text="エラー: URLが指定されていません")]
    
    try:
        # URLの検証
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return [TextContent(type="text", text="エラー: 無効なURLです")]
        
        # ファイル名の決定
        if not filename:
            # URLからファイル名を抽出
            path = Path(parsed_url.path)
            if path.suffix.lower() == '.pdf':
                filename = path.name
            else:
                filename = f"{path.stem or 'document'}.pdf"
        
        # 保存先ディレクトリの決定
        base_dir = CONFIG.get("download_base_dir")
        if base_dir:
            save_dir = Path(base_dir)
            
            # サブディレクトリが指定されている場合
            if subdir and CONFIG.get("allowed_subdirs", True):
                # パストラバーサル攻撃を防ぐため、相対パスのみ許可
                subdir_path = Path(subdir)
                if subdir_path.is_absolute() or ".." in subdir_path.parts:
                    return [TextContent(
                        type="text",
                        text="エラー: サブディレクトリには相対パスのみ指定できます（..は使用できません）"
                    )]
                save_dir = save_dir / subdir_path
            
            # ディレクトリが存在しない場合は作成
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            # ベースディレクトリが設定されていない場合は一時ディレクトリを使用
            save_dir = Path(tempfile.gettempdir())
            if subdir:
                return [TextContent(
                    type="text",
                    text="エラー: ベースディレクトリが設定されていないため、サブディレクトリは指定できません"
                )]
        
        save_path = save_dir / filename
        
        # 既存ファイルがある場合の処理
        if save_path.exists():
            base_name = save_path.stem
            extension = save_path.suffix
            counter = 1
            while save_path.exists():
                new_filename = f"{base_name}_{counter}{extension}"
                save_path = save_dir / new_filename
                counter += 1
        
        # PDFをダウンロード
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Content-Typeの確認
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
                return [TextContent(
                    type="text", 
                    text=f"警告: このURLはPDFファイルではない可能性があります (Content-Type: {content_type})"
                )]
            
            # ファイルに保存
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(response.content)
        
        file_size = save_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        return [TextContent(
            type="text",
            text=f"PDFダウンロード完了!\n"
                 f"URL: {url}\n"
                 f"保存先: {save_path.absolute()}\n"
                 f"ファイルサイズ: {file_size_mb:.2f} MB"
        )]
        
    except httpx.HTTPStatusError as e:
        return [TextContent(
            type="text",
            text=f"HTTPエラー: {e.response.status_code} - {e.response.reason_phrase}"
        )]
    except httpx.TimeoutException:
        return [TextContent(
            type="text",
            text="エラー: ダウンロードがタイムアウトしました"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"エラー: {str(e)}"
        )]


async def main():
    """メイン関数 - MCPサーバーを起動"""
    # 設定を読み込む
    load_config()
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

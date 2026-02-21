import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
import aiofiles
import httpx
import pymupdf4llm
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
server = Server("pdf-processor")


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
            name="pdf_to_markdown",
            description="PDFファイルをマークダウン形式に変換します。PyMuPDF4LLMを使用してテキスト、表、画像を含む高品質な変換を行います。",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "変換するPDFファイルのパス"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "出力するマークダウンファイルのパス（オプション）。指定しない場合はPDFと同じディレクトリに.mdファイルを作成"
                    },
                    "pages": {
                        "type": "string",
                        "description": "変換するページ範囲（例: '1-5', '1,3,5', 'all'）。デフォルトは'all'"
                    },
                    "extract_images": {
                        "type": "boolean",
                        "description": "画像を抽出するかどうか。デフォルトはtrue"
                    }
                },
                "required": ["pdf_path"]
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
    elif name == "pdf_to_markdown":
        return await pdf_to_markdown_tool(arguments)
    elif name == "get_download_config":
        return await get_download_config_tool()
    else:
        raise ValueError(f"Unknown tool: {name}")


async def pdf_to_markdown_tool(arguments: dict) -> list[TextContent]:
    """PDFからマークダウンへの変換ツールの実装"""
    pdf_path = arguments.get("pdf_path")
    output_path = arguments.get("output_path")
    pages = arguments.get("pages", "all")
    extract_images = arguments.get("extract_images", True)
    
    if not pdf_path:
        return [TextContent(type="text", text="エラー: PDFファイルのパスが指定されていません")]
    
    try:
        # PDFファイルの存在確認
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            return [TextContent(type="text", text=f"エラー: PDFファイルが見つかりません: {pdf_path}")]
        
        if not pdf_file.suffix.lower() == '.pdf':
            return [TextContent(type="text", text="エラー: 指定されたファイルはPDFファイルではありません")]
        
        # 出力パスの決定
        if not output_path:
            output_path = pdf_file.with_suffix('.md')
        else:
            output_path = Path(output_path)
            # 出力ディレクトリが存在しない場合は作成
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ページ範囲の解析
        page_list = None
        if pages and pages.lower() != "all":
            try:
                page_list = parse_page_range(pages)
            except ValueError as e:
                return [TextContent(type="text", text=f"エラー: ページ範囲の指定が無効です: {e}")]
        
        # PyMuPDF4LLMを使用してPDFをマークダウンに変換
        markdown_text = pymupdf4llm.to_markdown(
            str(pdf_file),
            pages=page_list,
            write_images=extract_images,
            image_path=str(output_path.parent) if extract_images else None,
            image_format="png",
            dpi=150
        )
        
        # マークダウンファイルに保存
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_text)
        
        # 統計情報の取得
        line_count = len(markdown_text.split('\n'))
        char_count = len(markdown_text)
        file_size = output_path.stat().st_size
        
        result_text = f"PDFからマークダウンへの変換完了!\n"
        result_text += f"入力ファイル: {pdf_file.absolute()}\n"
        result_text += f"出力ファイル: {output_path.absolute()}\n"
        result_text += f"変換ページ: {pages}\n"
        result_text += f"画像抽出: {'有効' if extract_images else '無効'}\n"
        result_text += f"出力統計:\n"
        result_text += f"  - 行数: {line_count:,}\n"
        result_text += f"  - 文字数: {char_count:,}\n"
        result_text += f"  - ファイルサイズ: {file_size / 1024:.1f} KB"
        
        return [TextContent(type="text", text=result_text)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"エラー: PDFの変換中にエラーが発生しました: {str(e)}")]


def parse_page_range(pages_str: str) -> list[int]:
    """ページ範囲文字列を解析してページ番号のリストを返す"""
    pages = []
    
    for part in pages_str.split(','):
        part = part.strip()
        if '-' in part:
            # 範囲指定（例: "1-5"）
            start, end = part.split('-', 1)
            start = int(start.strip())
            end = int(end.strip())
            if start > end:
                raise ValueError(f"無効な範囲: {part}")
            pages.extend(range(start, end + 1))
        else:
            # 単一ページ（例: "3"）
            pages.append(int(part))
    
    # 重複を除去してソート
    return sorted(list(set(pages)))


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
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,  # リダイレクトを自動追跡
            max_redirects=10        # 最大リダイレクト回数
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # リダイレクト情報の取得
            final_url = str(response.url)
            redirect_count = len(response.history)
            
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
        
        result_text = f"PDFダウンロード完了!\n"
        result_text += f"元のURL: {url}\n"
        if redirect_count > 0:
            result_text += f"最終URL: {final_url}\n"
            result_text += f"リダイレクト回数: {redirect_count}\n"
        result_text += f"保存先: {save_path.absolute()}\n"
        result_text += f"ファイルサイズ: {file_size_mb:.2f} MB"
        
        return [TextContent(type="text", text=result_text)]
        
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTPエラー: {e.response.status_code} - {e.response.reason_phrase}"
        
        # 301/302などのリダイレクトエラーの場合、追加情報を提供
        if e.response.status_code in [301, 302, 303, 307, 308]:
            location = e.response.headers.get('location', 'なし')
            error_msg += f"\nリダイレクト先: {location}"
            error_msg += f"\n注意: follow_redirects=Trueが設定されていますが、リダイレクトに失敗しました。"
            error_msg += f"\nURLを確認するか、リダイレクト先のURLを直接使用してください。"
        
        return [TextContent(type="text", text=error_msg)]
    except httpx.TooManyRedirects:
        return [TextContent(
            type="text",
            text="エラー: リダイレクトが多すぎます。無限リダイレクトループの可能性があります。"
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


def main_sync():
    """uvx用の同期エントリーポイント"""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())

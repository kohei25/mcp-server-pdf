from pathlib import Path
from urllib.parse import urlparse

import aiofiles
import httpx
from loguru import logger
from mcp.types import TextContent

from mcp_server_pdf.validation import validate_url


async def download_pdf_tool(arguments: dict) -> list[TextContent]:
    """PDFダウンロードツールの実装"""
    url = arguments.get("url")
    filename = arguments.get("filename")
    download_dir = arguments.get("download_dir")

    if not url:
        return [TextContent(type="text", text="エラー: URLが指定されていません")]

    try:
        # URLの検証（SSRF対策を含む）
        url_error = validate_url(url)
        if url_error:
            return [TextContent(type="text", text=url_error)]

        parsed_url = urlparse(url)

        # ファイル名の決定
        if not filename:
            path = Path(parsed_url.path)
            if path.suffix.lower() == ".pdf":
                filename = path.name
            else:
                filename = f"{path.stem or 'document'}.pdf"

        # 保存先ディレクトリの決定
        if download_dir:
            save_dir = Path(download_dir)
        else:
            save_dir = Path.cwd()

        save_dir.mkdir(parents=True, exist_ok=True)

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
            follow_redirects=True,
            max_redirects=10,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            final_url = str(response.url)
            redirect_count = len(response.history)

            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                return [
                    TextContent(
                        type="text",
                        text=f"警告: このURLはPDFファイルではない可能性があります (Content-Type: {content_type})",
                    )
                ]

            async with aiofiles.open(save_path, "wb") as f:
                await f.write(response.content)

        file_size = save_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        logger.info("PDFダウンロード完了: {} -> {}", url, save_path.absolute())

        result_text = "PDFダウンロード完了!\n"
        result_text += f"元のURL: {url}\n"
        if redirect_count > 0:
            result_text += f"最終URL: {final_url}\n"
            result_text += f"リダイレクト回数: {redirect_count}\n"
        result_text += f"保存先: {save_path.absolute()}\n"
        result_text += f"ファイルサイズ: {file_size_mb:.2f} MB"

        return [TextContent(type="text", text=result_text)]

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTPエラー: {e.response.status_code} - {e.response.reason_phrase}"

        if e.response.status_code in [301, 302, 303, 307, 308]:
            location = e.response.headers.get("location", "なし")
            error_msg += f"\nリダイレクト先: {location}"
            error_msg += "\n注意: follow_redirects=Trueが設定されていますが、リダイレクトに失敗しました。"
            error_msg += "\nURLを確認するか、リダイレクト先のURLを直接使用してください。"

        return [TextContent(type="text", text=error_msg)]
    except httpx.TooManyRedirects:
        return [
            TextContent(
                type="text",
                text="エラー: リダイレクトが多すぎます。無限リダイレクトループの可能性があります。",
            )
        ]
    except httpx.TimeoutException:
        return [
            TextContent(
                type="text",
                text="エラー: ダウンロードがタイムアウトしました",
            )
        ]
    except Exception as e:
        logger.exception("PDFダウンロード中に予期しないエラー")
        return [TextContent(type="text", text=f"エラー: {e}")]

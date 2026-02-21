from pathlib import Path

import aiofiles
from loguru import logger
from mcp.types import TextContent
import pymupdf4llm

from mcp_server_pdf.validation import parse_page_range


async def pdf_to_markdown_tool(arguments: dict) -> list[TextContent]:
    """PDFからマークダウンへの変換ツールの実装"""
    pdf_path = arguments.get("pdf_path")
    output_path = arguments.get("output_path")
    pages = arguments.get("pages", "all")
    extract_images = arguments.get("extract_images", True)

    if not pdf_path:
        return [TextContent(type="text", text="エラー: PDFファイルのパスが指定されていません")]

    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            return [
                TextContent(
                    type="text",
                    text=f"エラー: PDFファイルが見つかりません: {pdf_path}",
                )
            ]

        if pdf_file.suffix.lower() != ".pdf":
            return [TextContent(type="text", text="エラー: 指定されたファイルはPDFファイルではありません")]

        # 出力パスの決定
        if not output_path:
            output_path = pdf_file.with_suffix(".md")
        else:
            output_path = Path(output_path)
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
            dpi=150,
        )

        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(markdown_text)

        line_count = len(markdown_text.split("\n"))
        char_count = len(markdown_text)
        file_size = output_path.stat().st_size

        logger.info("PDF→Markdown変換完了: {} -> {}", pdf_file.absolute(), output_path.absolute())

        result_text = "PDFからマークダウンへの変換完了!\n"
        result_text += f"入力ファイル: {pdf_file.absolute()}\n"
        result_text += f"出力ファイル: {output_path.absolute()}\n"
        result_text += f"変換ページ: {pages}\n"
        result_text += f"画像抽出: {'有効' if extract_images else '無効'}\n"
        result_text += "出力統計:\n"
        result_text += f"  - 行数: {line_count:,}\n"
        result_text += f"  - 文字数: {char_count:,}\n"
        result_text += f"  - ファイルサイズ: {file_size / 1024:.1f} KB"

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.exception("PDF変換中に予期しないエラー")
        return [TextContent(type="text", text=f"エラー: PDFの変換中にエラーが発生しました: {e}")]

# MCP Server PDF

PDFのリンクからPDFファイルをダウンロードするMCPサーバーです。

## 機能

- PDFのURLからファイルをダウンロード
- ダウンロード先ディレクトリを指定可能（未指定時はカレントディレクトリに保存）
- 自動的なファイル名生成（URLから抽出）
- カスタムファイル名の指定
- 既存ファイルの重複回避（自動リネーム）
- PDFからMarkdownへの変換（PyMuPDF4LLM使用）
- Content-Typeの検証
- セキュリティ対策（SSRF防止）
- エラーハンドリング

## 使用方法

### MCPサーバーとして実行

#### uvコマンドで実行

```bash
uv run main.py
```

#### uvxコマンドで実行（推奨）

```bash
uvx --from . mcp-server-pdf

# または、GitHubから直接実行
uvx --from git+https://github.com/yourusername/mcp-server-pdf.git mcp-server-pdf
```

### Claude for Desktopでの設定

#### uvコマンドを使用する場合

Claude for Desktopの設定ファイル（`claude_desktop_config.json`）に以下を追加：

```json
{
  "mcpServers": {
    "pdf-downloader": {
      "command": "uv",
      "args": ["run", "main.py"],
      "cwd": "/path/to/mcp-server-pdf"
    }
  }
}
```

#### uvxコマンドを使用する場合（推奨）

```json
{
  "mcpServers": {
    "pdf-downloader": {
      "command": "uvx",
      "args": ["--from", "/path/to/mcp-server-pdf", "mcp-server-pdf"]
    }
  }
}
```

`cwd` を設定すると、`download_dir` 未指定時のデフォルト保存先がそのディレクトリになります。

## 利用可能なツール

### download_pdf

PDFのURLからファイルをダウンロードします。

**パラメータ:**
- `url` (必須): ダウンロードするPDFのURL
- `filename` (オプション): 保存するファイル名。指定しない場合はURLから自動生成
- `download_dir` (オプション): 保存先ディレクトリのパス。指定しない場合はカレントディレクトリに保存

**使用例:**

```
PDFをダウンロードしてください: https://example.com/document.pdf
```

```
PDFをダウンロードして、"research_paper.pdf"という名前で保存してください: https://example.com/paper.pdf
```

### pdf_to_markdown

PDFファイルをMarkdown形式に変換します。

**パラメータ:**
- `pdf_path` (必須): 変換するPDFファイルのパス
- `output_path` (オプション): 出力するMarkdownファイルのパス。指定しない場合はPDFと同じディレクトリに.mdファイルを作成
- `pages` (オプション): 変換するページ範囲（1始まり。例: '1-5', '1,3,5', 'all'）。デフォルトは'all'
- `extract_images` (オプション): 画像を抽出するかどうか。デフォルトはtrue

## 技術仕様

- Python 3.13+
- MCP (Model Context Protocol) 1.9.1+
- httpx for HTTP requests
- aiofiles for async file operations
- PyMuPDF4LLM for PDF to Markdown conversion

## エラーハンドリング

- 無効なURL
- HTTPエラー（404, 500など）
- タイムアウト
- ファイル保存エラー
- Content-Type検証
- SSRF防止（プライベートネットワークへのアクセスブロック）

## ライセンス

MIT License

# MCP Server PDF

PDFのリンクからPDFファイルをダウンロードするMCPサーバーです。

## 機能

- PDFのURLからファイルをダウンロード
- 環境変数、設定ファイル、またはコマンドライン引数でダウンロードディレクトリを指定
- 自動的なファイル名生成（URLから抽出）
- カスタムファイル名の指定
- サブディレクトリでの整理
- 既存ファイルの重複回避（自動リネーム）
- Content-Typeの検証
- セキュリティ対策（パストラバーサル攻撃防止）
- エラーハンドリング


## 設定

### 環境変数（推奨）

`PDF_DOWNLOAD_DIR` 環境変数でダウンロードディレクトリを指定できます：

```bash
export PDF_DOWNLOAD_DIR="/Users/username/Downloads/PDFs"
```

### 設定ファイル

`config.json`ファイルを作成してダウンロード設定を管理できます：

```json
{
  "download_base_dir": "/Users/username/Downloads/PDFs",
  "allowed_subdirs": true
}
```

**設定項目:**
- `download_base_dir`: ダウンロードファイルの保存先ベースディレクトリ（環境変数が優先）
- `allowed_subdirs`: サブディレクトリの作成を許可するか（true/false）

**設定の優先順位:**
1. 環境変数 `PDF_DOWNLOAD_DIR`
2. コマンドライン引数
3. 設定ファイル `config.json`

## 使用方法

### MCPサーバーとして実行

```bash
# 環境変数を設定して起動
export PDF_DOWNLOAD_DIR="/Users/username/Downloads/PDFs"
uv run main.py

# または、コマンドライン引数でディレクトリを指定
uv run main.py /Users/username/Downloads/PDFs
```

### Claude for Desktopでの設定

Claude for Desktopの設定ファイル（`claude_desktop_config.json`）に以下を追加：

```json
{
  "mcpServers": {
    "pdf-downloader": {
      "command": "uv",
      "args": ["run", "main.py"],
      "cwd": "/Users/niko/Dev/mcp-server-pdf",
      "env": {
        "PDF_DOWNLOAD_DIR": "/Users/niko/Downloads/PDFs"
      }
    }
  }
}
```

または、設定ファイルのみを使用する場合：

```json
{
  "mcpServers": {
    "pdf-downloader": {
      "command": "uv",
      "args": ["run", "main.py"],
      "cwd": "/Users/niko/Dev/mcp-server-pdf"
    }
  }
}
```

## 利用可能なツール

### download_pdf

PDFのURLからファイルをダウンロードします。設定されたベースディレクトリ以下に保存されます。

**パラメータ:**
- `url` (必須): ダウンロードするPDFのURL
- `filename` (オプション): 保存するファイル名
- `subdir` (オプション): ベースディレクトリ以下のサブディレクトリ名

**使用例:**

```
PDFをダウンロードしてください: https://example.com/document.pdf
```

```
PDFをダウンロードして、"research_paper.pdf"という名前で保存してください: https://example.com/paper.pdf
```

```
PDFをダウンロードして、~/Downloads/に保存してください: https://example.com/document.pdf
```

## 技術仕様

- Python 3.13+
- MCP (Model Context Protocol) 1.9.1+
- httpx for HTTP requests
- aiofiles for async file operations

## エラーハンドリング

- 無効なURL
- HTTPエラー（404, 500など）
- タイムアウト
- ファイル保存エラー
- Content-Type検証

## ライセンス

MIT License

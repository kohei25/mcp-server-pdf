import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> str | None:
    """URLを検証し、問題があればエラーメッセージを返す。問題なければNoneを返す。"""
    parsed = urlparse(url)

    if not parsed.scheme:
        return "エラー: 無効なURLです"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return f"エラー: 許可されていないURLスキームです（http/httpsのみ対応）: {parsed.scheme}"

    if not parsed.netloc:
        return "エラー: 無効なURLです"

    hostname = parsed.hostname
    if not hostname:
        return "エラー: URLにホスト名が含まれていません"

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return f"エラー: ホスト名を解決できません: {hostname}"

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return "エラー: プライベート/内部ネットワークへのアクセスは許可されていません"

    return None


def parse_page_range(pages_str: str) -> list[int]:
    """ページ範囲文字列を解析してページ番号のリストを返す。

    ユーザー入力は1-indexed（1始まり）で受け取り、
    PyMuPDF4LLMが期待する0-indexed（0始まり）に変換して返す。
    """
    pages = []

    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part and not part.startswith("-"):
            start, end = part.split("-", 1)
            start = int(start.strip())
            end = int(end.strip())
            if start < 1:
                raise ValueError(f"ページ番号は1以上を指定してください: {part}")
            if start > end:
                raise ValueError(f"無効な範囲: {part}")
            pages.extend(range(start, end + 1))
        else:
            page = int(part)
            if page < 1:
                raise ValueError(f"ページ番号は1以上を指定してください: {part}")
            pages.append(page)

    return sorted(set(p - 1 for p in pages))

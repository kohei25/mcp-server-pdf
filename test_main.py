import pytest

from mcp_server_pdf.validation import parse_page_range, validate_url


class TestValidateUrl:
    def test_valid_https_url(self):
        assert validate_url("https://example.com/file.pdf") is None

    def test_valid_http_url(self):
        assert validate_url("http://example.com/file.pdf") is None

    def test_empty_url(self):
        result = validate_url("")
        assert result is not None
        assert "無効なURL" in result

    def test_no_scheme(self):
        result = validate_url("example.com/file.pdf")
        assert result is not None

    def test_file_scheme_rejected(self):
        result = validate_url("file:///etc/passwd")
        assert result is not None
        assert "許可されていないURLスキーム" in result

    def test_ftp_scheme_rejected(self):
        result = validate_url("ftp://example.com/file.pdf")
        assert result is not None
        assert "許可されていないURLスキーム" in result

    def test_localhost_rejected(self):
        result = validate_url("http://localhost/secret")
        assert result is not None
        assert "プライベート" in result

    def test_loopback_ip_rejected(self):
        result = validate_url("http://127.0.0.1/secret")
        assert result is not None
        assert "プライベート" in result

    def test_private_ip_rejected(self):
        result = validate_url("http://192.168.1.1/secret")
        assert result is not None
        assert "プライベート" in result

    def test_link_local_rejected(self):
        result = validate_url("http://169.254.169.254/latest/meta-data/")
        assert result is not None
        assert "プライベート" in result

    def test_unresolvable_host(self):
        result = validate_url("https://this-host-does-not-exist-xyz123.example/file.pdf")
        assert result is not None
        assert "ホスト名を解決できません" in result


class TestParsePageRange:
    def test_single_page(self):
        assert parse_page_range("1") == [0]

    def test_single_page_higher(self):
        assert parse_page_range("5") == [4]

    def test_range(self):
        assert parse_page_range("1-3") == [0, 1, 2]

    def test_comma_separated(self):
        assert parse_page_range("1,3,5") == [0, 2, 4]

    def test_mixed_range_and_single(self):
        assert parse_page_range("1-3,7") == [0, 1, 2, 6]

    def test_duplicates_removed(self):
        assert parse_page_range("1,1,2") == [0, 1]

    def test_sorted_output(self):
        assert parse_page_range("5,1,3") == [0, 2, 4]

    def test_whitespace_handling(self):
        assert parse_page_range(" 1 , 3 - 5 ") == [0, 2, 3, 4]

    def test_invalid_range_reversed(self):
        with pytest.raises(ValueError, match="無効な範囲"):
            parse_page_range("5-3")

    def test_zero_page_rejected(self):
        with pytest.raises(ValueError, match="1以上"):
            parse_page_range("0")

    def test_negative_page_rejected(self):
        with pytest.raises(ValueError, match="1以上"):
            parse_page_range("-1")

    def test_non_numeric(self):
        with pytest.raises(ValueError):
            parse_page_range("abc")

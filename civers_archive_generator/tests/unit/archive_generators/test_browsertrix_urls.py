import pytest

from archive_generators.browsertrix.urls import normalize_http_url


@pytest.mark.parametrize("url,expected", [
    ("https://example.com", "https://example.com/"),
    ("HTTPS://EXAMPLE.COM:443#section", "https://example.com/"),
    ("http://Example.com:80/Article", "http://example.com/Article"),
    ("https://Example.com:8443/", "https://example.com:8443/"),
    ("http://[2001:DB8::1]:80", "http://[2001:db8::1]/"),
    ("https://bücher.example", "https://xn--bcher-kva.example/"),
    ("https://user:secret@EXAMPLE.COM", "https://user:secret@example.com/"),
    ("https://example.com?b=2&a=1#part", "https://example.com/?b=2&a=1"),
    ("https://example.com?#part", "https://example.com/?"),
])
def test_http_url_identity(url, expected):
    assert normalize_http_url(url) == expected
    assert normalize_http_url(expected) == expected


@pytest.mark.parametrize("first,second", [
    ("/article", "/article/"),
    ("/Article", "/article"),
    ("/?a=1", "/?a=2"),
    ("/?a=1&b=2", "/?b=2&a=1"),
    ("/a%2Fb", "/a/b"),
    ("/", "/?"),
])
def test_meaningful_url_differences_are_preserved(first, second):
    assert normalize_http_url("https://example.com" + first) != normalize_http_url("https://example.com" + second)


@pytest.mark.parametrize("url", ["/relative", "ftp://example.com", "https:///missing", "https://example.com:invalid"])
def test_non_http_or_malformed_urls_are_rejected(url):
    with pytest.raises(ValueError):
        normalize_http_url(url)

"""etl.acquire 安全核心的行为测试（零网络：resolver/fetcher 全部注入桩）。"""

import pytest

from etl.acquire import (
    FetchError,
    host_is_allowed,
    resolve_open_access,
    validate_public_http_url,
)


def fake_resolver(mapping: dict[str, list[str]]):
    """构造 hostname → IP 列表的桩 resolver；未登记的域名默认给公网地址。"""

    def resolve(host: str) -> list[str]:
        return mapping.get(host, ["93.184.216.34"])

    return resolve


class TestValidatePublicHttpUrl:
    def test_accepts_public_https_url(self):
        url = "https://api.crossref.org/works/10.1234/foo"
        assert (
            validate_public_http_url(url, resolver=fake_resolver({}))
            == url
        )

    def test_accepts_http_with_port_and_query(self):
        url = "http://example.org:8080/path?a=b"
        assert validate_public_http_url(url, resolver=fake_resolver({})) == url

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.org/file",
            "file:///etc/passwd",
            "gopher://example.org",
            "javascript:alert(1)",
        ],
    )
    def test_rejects_non_http_schemes(self, url):
        with pytest.raises(ValueError, match="scheme"):
            validate_public_http_url(url, resolver=fake_resolver({}))

    def test_rejects_url_without_host(self):
        with pytest.raises(ValueError, match="host"):
            validate_public_http_url("https:///no-host", resolver=fake_resolver({}))

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.0.0.5",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fd00::1",
        ],
    )
    def test_rejects_loopback_private_reserved(self, ip):
        resolver = fake_resolver({"internal.example": [ip]})
        with pytest.raises(ValueError, match="non-public"):
            validate_public_http_url(
                "https://internal.example/x", resolver=resolver
            )

    def test_rejects_literal_ip_url_in_private_range(self):
        with pytest.raises(ValueError, match="non-public"):
            validate_public_http_url(
                "http://192.168.0.10/api", resolver=fake_resolver({})
            )

    def test_rejects_literal_ipv6_loopback(self):
        with pytest.raises(ValueError, match="non-public"):
            validate_public_http_url("http://[::1]/x", resolver=fake_resolver({}))

    def test_rejects_host_that_resolves_to_nothing(self):
        with pytest.raises(ValueError, match="resolve"):
            validate_public_http_url(
                "https://void.example/x", resolver=lambda host: []
            )


class TestHostIsAllowed:
    ALLOWLIST = ("api.crossref.org", "api.unpaywall.org")

    def test_exact_match(self):
        assert host_is_allowed("api.crossref.org", self.ALLOWLIST)

    def test_subdomain_match(self):
        assert host_is_allowed("EU.api.crossref.org", self.ALLOWLIST)

    def test_case_and_trailing_dot_insensitive(self):
        assert host_is_allowed("API.Crossref.org.", self.ALLOWLIST)

    @pytest.mark.parametrize(
        "host",
        [
            "crossref.org",
            "notapicrossref.org",
            "api.crossref.org.evil.com",
            "",
        ],
    )
    def test_rejects_non_matching_hosts(self, host):
        assert not host_is_allowed(host, self.ALLOWLIST)


def stub_fetcher(responses: dict[str, object]):
    def fetch(url: str) -> object:
        return responses[url]

    return fetch


PUBLIC = {"api.crossref.org": ["93.184.216.34"], "api.unpaywall.org": ["93.184.216.34"]}
RESOLVER = fake_resolver(PUBLIC)


class TestResolveOpenAccess:
    DOI = "10.1234/abc.def"

    def make_fetcher(self, unpaywall_payload=None):
        return stub_fetcher(
            {
                f"https://api.crossref.org/works/{self.DOI}": {
                    "message": {
                        "title": ["Fuel cladding corrosion"],
                        "container-title": ["J. Nucl. Mater."],
                        "issued": {"date-parts": [[2023]]},
                    }
                },
                f"https://api.unpaywall.org/v2/{self.DOI}?email=tests@example.org": (
                    unpaywall_payload
                ),
            }
        )

    def test_full_resolution(self):
        result = resolve_open_access(
            self.DOI,
            fetcher=self.make_fetcher(
                {
                    "is_oa": True,
                    "best_oa_location": {"url": "https://repo.example/paper.pdf"},
                }
            ),
            email="tests@example.org",
            resolver=RESOLVER,
        )
        assert result["title"] == "Fuel cladding corrosion"
        assert result["journal"] == "J. Nucl. Mater."
        assert result["year"] == 2023
        assert result["is_oa"] is True
        assert result["best_oa_url"] == "https://repo.example/paper.pdf"
        assert result["errors"] == []

    def test_unpaywall_failure_degrades_to_metadata(self):
        def failing_unpaywall(url):
            if "unpaywall" in url:
                raise FetchError("down")
            return self.make_fetcher()(url)

        result = resolve_open_access(
            self.DOI, fetcher=failing_unpaywall, resolver=RESOLVER
        )
        assert result["title"] == "Fuel cladding corrosion"
        assert len(result["errors"]) == 1
        assert "unpaywall" in result["errors"][0]

    def test_doi_normalization_strips_prefix(self):
        fetcher = self.make_fetcher()
        result = resolve_open_access(
            " doi:10.1234/ABC.DEF ",
            fetcher=fetcher,
            email="tests@example.org",
            resolver=RESOLVER,
        )
        assert result["doi"] == "10.1234/abc.def"
        assert result["errors"] == []

    def test_empty_doi_rejected(self):
        with pytest.raises(ValueError, match="DOI"):
            resolve_open_access("   ", fetcher=stub_fetcher({}), resolver=RESOLVER)

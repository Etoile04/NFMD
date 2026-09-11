"""etl.acquire 安全核心的行为测试（零网络：resolver/fetcher 全部注入桩）。"""

import json
import stat
import zipfile
from pathlib import Path

import pytest

from etl.acquire import (
    FetchError,
    host_is_allowed,
    list_archive_members,
    resolve_open_access,
    restore_fulltext_from_archive,
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


SLUG = "10_1016_j_nucengdes_2018_01_045"
GOOD_MEMBER = f"raw/mineru/{SLUG}/auto/{SLUG}.md"


def make_archive(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    return str(path)


class TestRestoreFulltextFromArchive:
    @pytest.fixture()
    def archive(self, tmp_path):
        return make_archive(
            tmp_path / "raw.zip",
            {
                GOOD_MEMBER: "# fulltext body\n",
                f"raw/mineru/{SLUG}/auto/layout.json": "{}",
                f"raw/mineru/{SLUG}/auto/figure1.png": b"\x89PNG",
                "raw/mineru/other_slug/auto/other.md": "# other\n",
                "__MACOSX/raw/mineru/evil": b"junk",
                f"raw/mineru/{SLUG}/._resource": b"junk",
            },
        )

    @pytest.fixture()
    def wiki_root(self, tmp_path, monkeypatch):
        root = tmp_path / "wiki"
        root.mkdir()
        monkeypatch.setenv("NFMD_OUTPUT_ALLOWLIST", str(root))
        return str(root)

    def test_restores_only_slug_text_members(self, archive, wiki_root):
        result = restore_fulltext_from_archive(
            SLUG, archive_path=archive, wiki_root=wiki_root
        )
        assert sorted(result["restored"]) == [
            GOOD_MEMBER,
            f"raw/mineru/{SLUG}/auto/layout.json",
        ]
        body = Path(wiki_root, *GOOD_MEMBER.split("/")).read_text()
        assert body == "# fulltext body\n"
        assert not Path(wiki_root, "raw", "mineru", "other_slug").exists()

    def test_skips_existing_then_overwrites(self, archive, wiki_root):
        first = restore_fulltext_from_archive(
            SLUG, archive_path=archive, wiki_root=wiki_root
        )
        second = restore_fulltext_from_archive(
            SLUG, archive_path=archive, wiki_root=wiki_root
        )
        assert first["restored"] and second["restored"] == []
        assert sorted(second["skipped"]) == sorted(first["restored"])
        third = restore_fulltext_from_archive(
            SLUG, archive_path=archive, wiki_root=wiki_root, overwrite=True
        )
        assert sorted(third["restored"]) == sorted(first["restored"])

    def test_unknown_slug_raises(self, archive, wiki_root):
        with pytest.raises(ValueError, match="No fulltext members"):
            restore_fulltext_from_archive(
                "10_9999_missing", archive_path=archive, wiki_root=wiki_root
            )

    def test_invalid_slug_rejected(self, archive, wiki_root):
        for bad in ("../etc", "UPPER_SLUG", "slug;rm", ""):
            with pytest.raises(ValueError, match="[Ii]nvalid literature slug"):
                list_archive_members(archive, bad)

    def test_traversal_member_hard_fails(self, tmp_path, wiki_root):
        archive = make_archive(
            tmp_path / "evil.zip",
            {f"raw/mineru/{SLUG}/auto/{SLUG}.md": "# ok\n",
             f"raw/mineru/{SLUG}/../../escape.md": "# evil\n"},
        )
        with pytest.raises(ValueError, match="escapes target dir"):
            restore_fulltext_from_archive(
                SLUG, archive_path=archive, wiki_root=wiki_root
            )

    def test_symlink_member_hard_fails(self, tmp_path, wiki_root):
        zip_path = tmp_path / "link.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo(GOOD_MEMBER)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "/etc/passwd")
        with pytest.raises(ValueError, match="symlink"):
            restore_fulltext_from_archive(
                SLUG, archive_path=str(zip_path), wiki_root=wiki_root
            )

    def test_cli_restore(self, archive, wiki_root, capsys):
        from etl.acquire import main

        assert main(["restore", "--slug", SLUG, "--archive", archive,
                     "--wiki-root", wiki_root]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["slug"] == SLUG and payload["restored"] == 2

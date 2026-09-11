"""文献获取后备路径的安全核心（spec #9 WP4 / NFMA-6）。

纯校验与解析逻辑，不内建网络客户端：DNS 解析器与 JSON fetcher
均经参数注入，默认实现分别基于 socket 与 urllib（零新依赖，
ADR-0002）。真实抓取入口由调用方组装：先 ``validate_public_http_url``
（SSRF 防护），再按 ``host_is_allowed`` 的域名 allowlist 把关，
重定向跟随前对目标 URL 复检同一校验。
"""

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

from etl.path_safety import safe_write_path

# DNS 解析器：hostname → IP 地址字符串列表
HostResolver = Callable[[str], list[str]]

DEFAULT_RESOLVER_TIMEOUT = 5.0
USER_AGENT = "NFMD-acquire/0.1 (literature acquisition; contact: nfmd-admin@localhost)"


def _default_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve host: {host!r}") from e
    return [info[4][0] for info in infos]


def _address_is_public(ip_text: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return not (
        addr.is_loopback
        or addr.is_private
        or addr.is_reserved
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_public_http_url(url: str, *, resolver: HostResolver | None = None) -> str:
    """校验 URL 仅指向公网 http/https 目标，通过则原样返回。

    拒绝：非 http/https scheme、缺 host、无法解析的 host、
    以及解析到环回/私有/保留/链路本地/组播/未指定地址的目标
    （SSRF 防护；字面量 IP 主机同样受检）。
    """
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme not allowed: {parts.scheme!r} ({url!r})")
    host = parts.hostname
    if not host:
        raise ValueError(f"URL has no host: {url!r}")

    # 字面量 IP 主机直接受检（不经 resolver，杜绝桩解析器放行私有字面量）
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    ips = [str(literal)] if literal is not None else (resolver or _default_resolver)(host)
    if not ips:
        raise ValueError(f"URL host does not resolve: {host!r} ({url!r})")
    for ip in ips:
        if not _address_is_public(ip):
            raise ValueError(f"URL host resolves to non-public address {ip}: {url!r}")
    return url.strip()


def host_is_allowed(hostname: str, allowlist: Iterable[str]) -> bool:
    """域名 allowlist：精确匹配或点边界的子域匹配。"""
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    for entry in allowlist:
        allowed = entry.strip().lower().rstrip(".")
        if not allowed:
            continue
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


class FetchError(RuntimeError):
    """fetcher 获取失败（网络/HTTP 错误）。"""


def _urllib_fetch_json(url: str, timeout: float = 10.0) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        raise FetchError(f"GET {url} failed: {e}") from e


# JSON fetcher：url → 已解析的 JSON 对象
JsonFetcher = Callable[[str], object]


def normalize_doi(doi: str) -> str:
    """归一 DOI：去空白、去 doi: 前缀、转小写。"""
    cleaned = (doi or "").strip()
    if cleaned.lower().startswith("doi:"):
        cleaned = cleaned[4:].strip()
    return cleaned.lower()


def resolve_open_access(
    doi: str,
    *,
    fetcher: JsonFetcher | None = None,
    email: str = "nfmd-admin@localhost",
    resolver: HostResolver | None = None,
) -> dict:
    """DOI → 开放元数据 + 最佳 OA 副本 URL（Crossref + Unpaywall）。

    两个源独立尽力而为：单源失败不致命，错误记入 ``errors``；
    构造出的 API URL 本身也过 SSRF 校验（纵深防御）。
    """
    normalized = normalize_doi(doi)
    if not normalized:
        raise ValueError("Empty DOI")

    fetch = fetcher or _urllib_fetch_json
    result: dict = {"doi": normalized, "errors": []}

    # Crossref：元数据
    crossref_url = f"https://api.crossref.org/works/{normalized}"
    try:
        validate_public_http_url(crossref_url, resolver=resolver)
        message = (fetch(crossref_url) or {}).get("message", {})
        result["title"] = (message.get("title") or [None])[0]
        result["journal"] = (message.get("container-title") or [None])[0]
        issued = message.get("issued", {}).get("date-parts") or [[None]]
        result["year"] = issued[0][0]
    except (ValueError, FetchError, AttributeError) as e:
        result["errors"].append(f"crossref: {e}")

    # Unpaywall：最佳 OA 副本
    unpaywall_url = f"https://api.unpaywall.org/v2/{normalized}?email={email}"
    try:
        validate_public_http_url(unpaywall_url, resolver=resolver)
        payload = fetch(unpaywall_url) or {}
        best = payload.get("best_oa_location") or {}
        result["best_oa_url"] = best.get("url")
        result["is_oa"] = bool(payload.get("is_oa"))
    except (ValueError, FetchError, AttributeError) as e:
        result["errors"].append(f"unpaywall: {e}")

    return result


# ---------------------------------------------------------------------------
# 全文层按需恢复（NFMA-10，试点结论转化）：从归档（raw.zip）恢复 MinerU
# 全文到语料根的规范路径 raw/mineru/<slug>/…，作为获取层在本地库/开放 API
# 之外的就近后备——产物只是落盘文件，仍走既有 extract→validate 管线。
# 安全模型与 etl.path_safety 同构：成员名 normpath 后禁止父目录引用段，
# realpath 解析后限制在 wiki_root 内；落盘前再过一次 safe_write_path
# （仓库外语料根需在 NFMD_OUTPUT_ALLOWLIST 登记）。
# ---------------------------------------------------------------------------

# DOI slug 形态：10_1016_j_nucengdes_2018_01_045（小写字母数字与 _ . -）
_SLUG_RE = re.compile(r"^[0-9a-z][0-9a-z._-]*$")

# 仅恢复文本类全文资产（MinerU markdown 及其伴随文本），图片等不在此列
_MEMBER_SUFFIX_ALLOWLIST = {".md", ".txt", ".json"}
_MEMBER_SIZE_LIMIT = 64 * 1024 * 1024  # 单成员解压上限（防 zip bomb）
_TOTAL_SIZE_LIMIT = 128 * 1024 * 1024  # 单次恢复累计上限


def _sanitize_member_name(name: str) -> str:
    """zip 成员路径校验：拒绝绝对路径、盘符、NUL 与父目录引用段。

    先检查原始段再 normpath——normpath 会折叠内层父目录引用，先查才能
    让任何含 ``..`` 的成员显式失败而不是静默改道。
    """
    if not name or "\x00" in name:
        raise ValueError(f"Invalid archive member name: {name!r}")
    segments = [s for s in name.replace("\\", "/").split("/") if s]
    if any(s == os.pardir for s in segments):
        raise ValueError(f"Archive member escapes target dir: {name!r}")
    normalized = os.path.normpath("/".join(segments))
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"Archive member is an absolute path: {name!r}")
    return normalized


def _is_junk_member(name: str) -> bool:
    """macOS 打包垃圾（__MACOSX 段、 ._ 资源叉文件）。"""
    segments = name.split("/")
    return any(s == "__MACOSX" for s in segments) or any(
        s.startswith("._") for s in segments if s
    )


def _member_destination(wiki_root: str, member: str) -> str:
    """成员名 → 校验后的落盘绝对路径：realpath 解析并限制在 wiki_root 内。"""
    root_real = os.path.realpath(wiki_root)
    candidate = os.path.normpath(os.path.join(root_real, member))
    if not (candidate == root_real or candidate.startswith(root_real + os.sep)):
        raise ValueError(f"Archive member escapes wiki root: {member!r}")
    return candidate


def list_archive_members(archive_path: str, slug: str) -> list[str]:
    """列出归档中 raw/mineru/<slug>/ 下可恢复的文本成员（已过滤目录与垃圾项）。

    任何成员名越界（绝对路径/父目录引用）、符号链接成员或超限成员都会使
    整个列举失败——恢复操作不容许部分放行。
    """
    if not _SLUG_RE.match(slug or ""):
        raise ValueError(f"Invalid literature slug: {slug!r}")
    prefix = f"raw/mineru/{slug}/"
    members: list[str] = []
    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            name = _sanitize_member_name(info.filename)
            if _is_junk_member(name) or not name.startswith(prefix):
                continue
            if name.endswith("/"):
                continue  # 目录项
            if Path(name).suffix.lower() not in _MEMBER_SUFFIX_ALLOWLIST:
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"Archive member is a symlink: {info.filename!r}")
            if info.file_size > _MEMBER_SIZE_LIMIT:
                raise ValueError(
                    f"Archive member too large ({info.file_size} bytes): {info.filename!r}"
                )
            members.append(name)
    return members


def restore_fulltext_from_archive(
    slug: str,
    *,
    archive_path: str,
    wiki_root: str,
    overwrite: bool = False,
) -> dict:
    """按需恢复：把归档中该文献的全文文本解压到 wiki_root 的规范路径。

    返回 ``{"restored": [...], "skipped": [...]}``；已存在且未要求覆盖的
    成员跳过。
    """
    members = list_archive_members(archive_path, slug)
    if not members:
        raise ValueError(f"No fulltext members for slug {slug!r} in {archive_path}")

    restored: list[str] = []
    skipped: list[str] = []
    total = 0
    with zipfile.ZipFile(archive_path) as zf:
        for name in members:
            destination = safe_write_path(_member_destination(wiki_root, name))
            if os.path.exists(destination) and not overwrite:
                skipped.append(name)
                continue
            total += zf.getinfo(name).file_size
            if total > _TOTAL_SIZE_LIMIT:
                raise ValueError(
                    f"Cumulative restore size exceeds limit at member {name!r}"
                )
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with zf.open(name) as src, Path(destination).open("wb") as dst:
                shutil.copyfileobj(src, dst)
            restored.append(name)
    return {"restored": restored, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="文献获取后备路径（本地库/开放 API 之外的就近恢复）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_restore = sub.add_parser("restore", help="从 raw.zip 按需恢复全文到语料根")
    p_restore.add_argument(
        "--slug", required=True, help="文献 slug（如 10_1016_j_nucengdes_2018_01_045）"
    )
    p_restore.add_argument("--archive", required=True, help="归档路径（raw.zip）")
    p_restore.add_argument("--wiki-root", required=True, help="语料根（解压落盘根）")
    p_restore.add_argument("--overwrite", action="store_true", help="覆盖已存在文件")

    args = parser.parse_args(argv)
    if args.cmd == "restore":
        result = restore_fulltext_from_archive(
            args.slug,
            archive_path=args.archive,
            wiki_root=args.wiki_root,
            overwrite=args.overwrite,
        )
        print(
            json.dumps(
                {
                    "slug": args.slug,
                    "restored": len(result["restored"]),
                    "skipped": len(result["skipped"]),
                    "files": result["restored"],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

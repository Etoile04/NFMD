"""文献获取后备路径的安全核心（spec #9 WP4 / NFMA-6）。

纯校验与解析逻辑，不内建网络客户端：DNS 解析器与 JSON fetcher
均经参数注入，默认实现分别基于 socket 与 urllib（零新依赖，
ADR-0002）。真实抓取入口由调用方组装：先 ``validate_public_http_url``
（SSRF 防护），再按 ``host_is_allowed`` 的域名 allowlist 把关，
重定向跟随前对目标 URL 复检同一校验。
"""

import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable

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

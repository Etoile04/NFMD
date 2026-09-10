"""写路径安全入口（NFMA-2，Mimosa CWE-22 整改）。

集中承接 ETL 各阶段的文件写入：规范化拒绝父目录引用段与 NUL，
realpath 解析后限制在允许目录内（默认当前工作目录；用
NFMD_OUTPUT_ALLOWLIST 环境变量按 os.pathsep 分隔追加仓库外根，
如语料目录或报告输出根）。本地 CLI 场景，不面向服务端请求。
"""

import os
import tempfile
from pathlib import Path


def _assert_no_parent_refs(path: str) -> str:
    """校验并规范化路径：拒绝空值、NUL 与任何父目录引用段。"""
    if not path or not isinstance(path, str):
        raise ValueError(f"Invalid path: {path!r}")
    if "\x00" in path:
        raise ValueError(f"NUL byte in path: {path!r}")
    normalized = os.path.normpath(path)
    segments = [s for s in normalized.replace("\\", "/").split("/") if s]
    if any(s == os.pardir for s in segments):
        raise ValueError(f"Path traversal not allowed: {path!r}")
    return normalized


def _allowlist_roots() -> list[str]:
    """允许根：环境变量 NFMD_OUTPUT_ALLOWLIST（os.pathsep 分隔）覆盖；
    默认当前工作目录 + 系统临时目录（测试与中间产物落点）。"""
    roots_raw = os.environ.get("NFMD_OUTPUT_ALLOWLIST")
    if roots_raw is not None:
        candidates = roots_raw.split(os.pathsep)
    else:
        candidates = [os.getcwd(), tempfile.gettempdir()]
    return [os.path.realpath(r) for r in candidates if r.strip()]


def safe_write_path(path: str) -> str:
    """返回校验通过的绝对写路径；白名单外抛 ValueError。"""
    candidate = _assert_no_parent_refs(path)
    resolved = os.path.realpath(candidate)
    roots = _allowlist_roots()
    if not any(resolved == root or resolved.startswith(root + os.sep) for root in roots):
        raise ValueError(f"Output path outside allowlist: {path!r} (allowed roots: {roots})")
    return resolved


def safe_read_path(path: str) -> str:
    """返回校验通过的读路径（规范化，拒绝穿越段）。"""
    return _assert_no_parent_refs(path)


def safe_open_write(path: str) -> object:
    """校验后以文本写模式打开，返回文件对象。"""
    validated = safe_write_path(path)
    return Path(validated).open("w", encoding="utf-8")


def safe_open_read(path: str) -> object:
    """校验后以文本读模式打开，返回文件对象。"""
    validated = safe_read_path(path)
    return Path(validated).open(encoding="utf-8")

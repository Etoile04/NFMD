"""ChatExtract 式 confidence 推导规则（NFMA-2，调研报告 §4.1.1）。

来源：Polak et al., Nat Commun 15, 2024（对话式 LLM 材料数值抽取的
prompt 工程协议）。协议三要素：① 抽取问题与原文句子分离；② 双通道
独立抽取（同一数据点问两次）；③ 自审计追问（对每个抽取做 yes/no 级
验证）。本模块把协议固化为 confidence 判据，供 extract 阶段对携带
双通道/自审计元数据的上游（llm-wiki）记录推导 confidence：

- 双通道一致 + 自审计通过       → high
- 双通道一致 + 自审计存疑/缺失  → medium
- 双通道不一致                 → low
- 单通道 + 自审计通过          → medium
- 单通道 + 自审计存疑/缺失     → low
- 无通道元数据                 → None（回退到记录自带 confidence 标签）

prompt 模板见 :mod:`etl.prompts`（供上游 llm-wiki 产出双通道与自审计
字段）；LLM 输出仍必须走 validate 全量规则校验，不因 confidence=high
跳过任何规则。
"""

from collections.abc import Mapping
from typing import Any

# 自审计答案的规范化
_AUDIT_PASS_TOKENS = {"pass", "passed", "yes", "true", "y", "ok"}
_AUDIT_DOUBT_TOKENS = {"doubt", "failed", "no", "false", "n", "uncertain"}

# 数值 confidence（上游 0-1 分）到标签的映射阈值
NUMERIC_HIGH_THRESHOLD = 0.85
NUMERIC_MEDIUM_THRESHOLD = 0.6

VALID_LABELS = frozenset({"high", "medium", "low"})


def normalize_audit(raw: Any) -> str | None:
    """把自审计原始回答归一化为 ``pass`` / ``doubt`` / None。"""
    if raw is None:
        return None
    token = str(raw).strip().lower()
    if token in _AUDIT_PASS_TOKENS:
        return "pass"
    if token in _AUDIT_DOUBT_TOKENS:
        return "doubt"
    return None


def channels_agree(channel_a: Any, channel_b: Any) -> bool | None:
    """双通道答案是否一致；任一通道缺失返回 None。"""
    if channel_a is None or channel_b is None:
        return None

    def canon(value: Any) -> str | None:
        if isinstance(value, Mapping):
            value = value.get("value")
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    a, b = canon(channel_a), canon(channel_b)
    if a is None or b is None:
        return None
    return a == b


def derive_confidence(channel_a: Any, channel_b: Any, self_audit: Any) -> str | None:
    """按 ChatExtract 判据推导 confidence 标签。"""
    audit = normalize_audit(self_audit)
    agree = channels_agree(channel_a, channel_b)

    if agree is True:
        return "high" if audit == "pass" else "medium"
    if agree is False:
        return "low"
    # 单通道（另一通道缺失）
    has_single = channel_a is not None or channel_b is not None
    if has_single:
        return "medium" if audit == "pass" else "low"
    return None


def normalize_confidence_label(raw: Any) -> str | None:
    """归一化记录自带的 confidence：high/medium/low 标签或 0-1 数值分。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        score = float(raw)
        if not 0.0 <= score <= 1.0:
            return None
        if score >= NUMERIC_HIGH_THRESHOLD:
            return "high"
        if score >= NUMERIC_MEDIUM_THRESHOLD:
            return "medium"
        return "low"
    token = str(raw).strip().lower()
    if token in ("high", "h"):
        return "high"
    if token in ("medium", "med", "m"):
        return "medium"
    if token in ("low", "l"):
        return "low"
    return None

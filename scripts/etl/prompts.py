"""ChatExtract 协议 prompt 模板（NFMA-2，调研报告 §4.1.1）。

供上游 llm-wiki 抽取使用：同一数据点用 :data:`EXTRACTION_CHANNEL_PROMPT`
独立抽取两次（channel_a / channel_b，两次对话互不可见），再用
:data:`SELF_AUDIT_PROMPT` 对抽取结果做 yes/no 级自审计。产出的
``channel_a`` / ``channel_b`` / ``self_audit`` 三字段随记录 JSON 进入
ETL extract 阶段，由 :mod:`etl.confidence` 推导 confidence。
"""

EXTRACTION_CHANNEL_PROMPT = """\
You are extracting one numerical material property value from a research paper.

[QUESTION]
{question}

[SOURCE SENTENCE]
{source_sentence}

Rules:
1. Answer using ONLY the source sentence above. Do not use any prior context
   or knowledge.
2. Return a JSON object with exactly one key "value" holding the extracted
   value (number, range [min, max], or expression string), or null if the
   sentence does not contain the answer.
3. Do not paraphrase, convert units, or infer values that are not stated.
"""

SELF_AUDIT_PROMPT = """\
Verify the following extraction against its source sentence.

[EXTRACTED VALUE]
{value}

[QUESTION]
{question}

[SOURCE SENTENCE]
{source_sentence}

Answer with exactly one word:
- "yes" if the extracted value is stated in the source sentence and answers
  the question as-is (same quantity, same unit, no interpretation);
- "no" otherwise (wrong number, unit mismatch, misread range, or inferred).
"""

__all__ = ["EXTRACTION_CHANNEL_PROMPT", "SELF_AUDIT_PROMPT"]

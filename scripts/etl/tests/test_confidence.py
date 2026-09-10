"""Tests for ChatExtract confidence derivation rules and prompt templates."""

from etl.confidence import (
    channels_agree,
    derive_confidence,
    normalize_audit,
    normalize_confidence_label,
)
from etl.prompts import EXTRACTION_CHANNEL_PROMPT, SELF_AUDIT_PROMPT


class TestNormalizeAudit:
    def test_pass_tokens(self):
        for raw in ("pass", "Yes", "YES", "true", "y", "ok"):
            assert normalize_audit(raw) == "pass"

    def test_doubt_tokens(self):
        for raw in ("no", "NO", "false", "doubt", "uncertain", "n"):
            assert normalize_audit(raw) == "doubt"

    def test_missing_or_unknown(self):
        assert normalize_audit(None) is None
        assert normalize_audit("") is None
        assert normalize_audit("maybe??") is None


class TestChannelsAgree:
    def test_both_present_agree(self):
        assert channels_agree("5.0", "5.0") is True
        assert channels_agree({"value": 5.0}, {"value": 5.0}) is True

    def test_both_present_disagree(self):
        assert channels_agree(5.0, 5.1) is False
        assert channels_agree({"value": 5.0}, {"value": "6.0"}) is False

    def test_whitespace_insensitive(self):
        assert channels_agree(" 5.0 ", "5.0") is True

    def test_missing_channel(self):
        assert channels_agree(None, "5.0") is None
        assert channels_agree("5.0", None) is None
        assert channels_agree(None, None) is None


class TestDeriveConfidence:
    def test_dual_channel_agree_audit_pass_is_high(self):
        assert derive_confidence(5.0, 5.0, "yes") == "high"

    def test_dual_channel_agree_audit_doubt_is_medium(self):
        assert derive_confidence(5.0, 5.0, "no") == "medium"

    def test_dual_channel_agree_audit_missing_is_medium(self):
        assert derive_confidence(5.0, 5.0, None) == "medium"

    def test_dual_channel_disagree_is_low_regardless_of_audit(self):
        assert derive_confidence(5.0, 6.0, "yes") == "low"
        assert derive_confidence(5.0, 6.0, None) == "low"

    def test_single_channel_audit_pass_is_medium(self):
        assert derive_confidence(5.0, None, "yes") == "medium"
        assert derive_confidence(None, 5.0, "yes") == "medium"

    def test_single_channel_audit_doubt_is_low(self):
        assert derive_confidence(5.0, None, "no") == "low"
        assert derive_confidence(None, 5.0, None) == "low"

    def test_no_metadata_is_none(self):
        assert derive_confidence(None, None, None) is None


class TestNormalizeConfidenceLabel:
    def test_labels(self):
        assert normalize_confidence_label("high") == "high"
        assert normalize_confidence_label("Medium") == "medium"
        assert normalize_confidence_label(" LOW ") == "low"
        assert normalize_confidence_label("h") == "high"

    def test_numeric_scores(self):
        assert normalize_confidence_label(0.9) == "high"
        assert normalize_confidence_label(0.7) == "medium"
        assert normalize_confidence_label(0.5) == "low"
        assert normalize_confidence_label(1.0) == "high"

    def test_out_of_range_or_invalid(self):
        assert normalize_confidence_label(1.5) is None
        assert normalize_confidence_label("None") is None
        assert normalize_confidence_label(None) is None


class TestPromptTemplates:
    def test_extraction_prompt_separates_question_and_sentence(self):
        rendered = EXTRACTION_CHANNEL_PROMPT.format(
            question="What is the swelling coefficient?",
            source_sentence="The swelling coefficient was measured as 5.0.",
        )
        assert "[QUESTION]" in rendered
        assert "[SOURCE SENTENCE]" in rendered
        assert "swelling coefficient" in rendered
        # 协议要求：只用原句、不做单位换算/推断
        assert "ONLY the source sentence" in rendered

    def test_self_audit_prompt_is_yes_no_level(self):
        rendered = SELF_AUDIT_PROMPT.format(
            value="5.0", question="q", source_sentence="s"
        )
        assert '"yes"' in rendered and '"no"' in rendered
        assert "[EXTRACTED VALUE]" in rendered

"""Validate: Apply rules to extracted records."""

from models import ExtractedRecord, ValidationIssue
from rules import ALL_RULES


def validate_records(
    records: list[ExtractedRecord], run_id: str
) -> tuple[list[ExtractedRecord], list[ExtractedRecord], list[ValidationIssue]]:
    """
    Validate records and separate into valid (may have warnings) and errored.
    Returns (valid_records, error_records, all_issues).
    """
    valid = []
    errored = []
    all_issues: list[ValidationIssue] = []

    for rec in records:
        record_issues = []
        has_error = False

        for rule in ALL_RULES:
            issues = rule.apply(rec, run_id)
            for issue in issues:
                if issue.severity == "error":
                    has_error = True
                record_issues.append(issue)

        all_issues.extend(record_issues)

        if has_error:
            errored.append(rec)
        else:
            valid.append(rec)

    return valid, errored, all_issues

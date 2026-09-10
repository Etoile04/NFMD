"""Transform: Normalize records for database loading."""


from etl.confidence import normalize_confidence_label
from etl.formula import FormulaNormalizer, build_formula_normalizer
from etl.models import ExtractedRecord, TransformedRecord
from etl.normalize import MaterialNormalizer, normalize_unit, parse_temperature


def transform_records(
    records: list[ExtractedRecord],
    material_norm: MaterialNormalizer,
    formula_norm: FormulaNormalizer | None = None,
) -> list[TransformedRecord]:
    """Transform extracted records into database-ready format.

    ``formula_norm`` 按接口注入（ADR-0005）：缺省时由工厂构建——
    装有 ``etl[chem]`` extras 用 pymatgen 引擎，否则降级为 stdlib
    正则引擎（行为差异见 etl.formula）。
    """
    if formula_norm is None:
        formula_norm = build_formula_normalizer()
    results = []
    for rec in records:
        transformed = _transform_one(rec, material_norm, formula_norm)
        if transformed:
            results.append(transformed)
    return results


def _transform_one(
    rec: ExtractedRecord,
    material_norm: MaterialNormalizer,
    formula_norm: FormulaNormalizer,
) -> TransformedRecord | None:
    """Transform a single record."""
    # Material normalization
    material_name = material_norm.normalize(rec.raw_material)
    # 化学式机械归一（pymatgen 引擎需 etl[chem] extras，注入式，见 ADR-0005）
    formula_result = formula_norm.normalize(rec.raw_material)

    # Temperature: use pre-extracted if available, otherwise parse
    temp_k = rec.temperature_K
    temp_str = rec.temperature_str
    if temp_k is None and rec.raw_temperature:
        parsed_k, parsed_str = parse_temperature(rec.raw_temperature)
        if parsed_k:
            temp_k = parsed_k
        if parsed_str:
            temp_str = parsed_str

    # Unit normalization
    unit = normalize_unit(rec.raw_unit)

    # Confidence：ChatExtract 推导结果优先（etl.confidence），缺失时回退
    # 到记录自带标签/数值分的归一化
    confidence = rec.derived_confidence or normalize_confidence_label(rec.raw_confidence)

    # Value decomposition
    value_scalar = rec.value_scalar
    value_min = rec.value_min
    value_max = rec.value_max
    value_expr = rec.value_expr
    value_list = rec.value_list
    value_text = rec.value_text
    value_str = rec.value_str or _make_value_str(rec)

    # Handle expression type: value might be in equation or value_str
    if rec.value_type == "expression" and not value_expr:
        if rec.equation and rec.equation not in ("Eq. 1", "Eq. 2", "Eq. 3"):
            value_expr = rec.equation
        elif isinstance(rec.raw_value, str):
            value_expr = rec.raw_value

    # Combine notes from multiple sources
    notes_parts = []
    if rec.notes:
        notes_parts.append(rec.notes)
    if rec.description:
        notes_parts.append(rec.description)
    if rec.phase:
        notes_parts.append(f"Phase: {rec.phase}")
    if rec.conditions:
        notes_parts.append(f"Conditions: {rec.conditions}")
    combined_notes = "; ".join(notes_parts) if notes_parts else None

    # Generate literature ID from source_file
    literature_id = _slug_from_source(rec.source_file)

    return TransformedRecord(
        id=rec.record_id,
        name=rec.name_en or rec.name,
        name_en=rec.name_en,
        name_zh=rec.name_zh or (rec.name if rec.name_en and rec.name != rec.name_en else None),
        symbol=rec.symbol,
        category=rec.category,
        subcategory=rec.subcategory,
        value_type=rec.value_type,
        value_scalar=value_scalar,
        value_min=value_min,
        value_max=value_max,
        value_expr=value_expr,
        value_list=value_list,
        value_text=value_text,
        value_str=value_str,
        unit=unit,
        uncertainty=rec.uncertainty if rec.uncertainty and rec.uncertainty != "None" else None,
        material_name=material_name,
        material_raw=rec.raw_material,
        material_formula=formula_result.formula,
        temperature_k=temp_k,
        temperature_str=temp_str,
        burnup_range=rec.raw_burnup,
        method=rec.raw_method,
        confidence=confidence,
        source_file=rec.source_file,
        equation=rec.equation,
        notes=combined_notes,
        literature_id=literature_id,
    )


def _normalize_confidence(raw) -> str | None:
    """归一化 confidence（已迁至 etl.confidence，保留薄封装供既有调用）。"""
    return normalize_confidence_label(raw)


def _make_value_str(rec: ExtractedRecord) -> str | None:
    """Generate value_str from available data."""
    if rec.value_str:
        return rec.value_str
    if rec.raw_value is not None:
        if isinstance(rec.raw_value, list):
            return ", ".join(str(v) for v in rec.raw_value)
        return str(rec.raw_value)
    return None


def _slug_from_source(source_file: str) -> str:
    """Generate a stable literature ID from source_file."""
    if not source_file:
        return "unknown"
    # Remove path and extension
    slug = source_file.replace("summaries/", "").replace("\\", "/").split("/")[-1]
    slug = slug.replace(".md", "").replace(".json", "").strip()
    # Truncate if too long
    if len(slug) > 120:
        slug = slug[:120]
    return slug

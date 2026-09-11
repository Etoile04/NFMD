"""人工专家金标标注器（annotation tooling, no ticket — board blocked by RE）。

规范见 ``docs/annotation/guideline.md``。三个纯函数接缝 + 本地 Web UI：

- :func:`build_record` / :func:`check_record` — 表单 → 金标记录 →
  ``etl.validate`` 规则引擎实时校验（标注即校验）；
- :func:`trim_source_sentence` — 划选文本 → 出处引用（纯函数）；
- :func:`pair_annotations` / :func:`arbitrate` — 双标注人记录 → 值级
  自动比对（复用 ``fulltext_pilot.values_match``）→ 仲裁合并 →
  ``gold/<slug>.json``，格式可直接被
  ``fulltext_pilot.evaluate_against_gold`` 消费；
- 导出一律经 ``path_safety`` 白名单校验。

零新依赖（ADR-0002）：FastAPI + stdlib，无数据库。启动::

    uv run python -m etl.annotate serve [--source-dir DIR] [--out-dir DIR]
"""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from etl.fulltext_pilot import values_match
from etl.io_utils import write_json
from etl.models import ExtractedRecord
from etl.normalize import normalize_unit
from etl.path_safety import safe_open_read, safe_read_path, safe_write_path
from etl.validate import validate_records

# 金标记录字段（guideline §2）；value 是给 values_match/evaluate 的便捷键
_GOLD_FIELDS = (
    "name_en", "name_zh", "symbol", "category", "value_type",
    "value_scalar", "value_min", "value_max", "value_expr", "value_list",
    "value_text", "value_str", "value",
    "unit", "unit_canonical", "uncertainty",
    "material", "temperature_K", "temperature_str", "burnup",
    "source_sentence", "source_location", "conditions", "notes", "equation",
)


def build_record(form: dict, *, slug: str, annotator: str, seq: int) -> dict:
    """表单 → 金标记录 dict（含 ``value`` 便捷键与 provenance）。"""
    rec: dict = {k: form.get(k) for k in _GOLD_FIELDS}
    vt = form.get("value_type")
    if vt == "scalar" and rec.get("value_scalar") is not None:
        rec["value"] = rec["value_scalar"]
    elif vt == "range" and rec.get("value_min") is not None:
        rec["value"] = [rec["value_min"], rec["value_max"]]
    elif vt == "list" and rec.get("value_list") is not None:
        rec["value"] = rec["value_list"]
    elif vt in ("expression", "text") and rec.get("value_str") is None:
        rec["value_str"] = rec.get("value_expr") or rec.get("value_text")
    if not rec.get("unit_canonical"):
        rec["unit_canonical"] = normalize_unit(rec.get("unit"))
    rec["record_id"] = f"{slug}_{annotator}_{seq:03d}"
    rec["source_file"] = slug
    rec["annotator"] = annotator
    # value_* 显式保留 None：金标 schema 的分列字段（ADR-0006 前向兼容）
    for k in ("value_scalar", "value_min", "value_max"):
        rec.setdefault(k, None)
    return rec


def check_record(rec: dict) -> list[dict]:
    """跑规则引擎，返回 issue dict 列表（severity/code/message）。"""
    extracted = ExtractedRecord(
        record_id=rec.get("record_id", ""),
        source_file=rec.get("source_file", ""),
        name_en=rec.get("name_en"),
        name=rec.get("name_zh") or "",
        category=rec.get("category", ""),
        value_type=rec.get("value_type", ""),
        raw_value=rec.get("value"),
        raw_material=rec.get("material"),
        raw_temperature=rec.get("temperature_K") or rec.get("temperature_str"),
        raw_burnup=rec.get("burnup"),
        raw_unit=rec.get("unit"),
        value_scalar=rec.get("value_scalar"),
        value_min=rec.get("value_min"),
        value_max=rec.get("value_max"),
        value_expr=rec.get("value_expr"),
        value_list=rec.get("value_list"),
        value_str=rec.get("value_str"),
        uncertainty=rec.get("uncertainty"),
    )
    _, _, issues = validate_records([extracted], run_id="annotate")
    return [
        {"severity": i.severity, "code": i.code, "message": i.message}
        for i in issues
    ]


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def trim_source_sentence(text: str, max_sentences: int = 2) -> str:
    """划选文本 → 出处引用：折叠空白，截断到 ≤2 句。"""
    collapsed = " ".join((text or "").split())
    if not collapsed:
        return ""
    sentences = _SENT_SPLIT.split(collapsed)
    return " ".join(sentences[:max_sentences])


def pair_annotations(records_a: list[dict], records_b: list[dict]) -> list[dict]:
    """双标注人记录 → 配对：值一致优先，名称精确匹配兜底（同 category）。"""
    pairs: list[dict] = []
    used_b: set[int] = set()

    def _match_key(r: dict):
        return (r.get("category"), (r.get("name_en") or "").strip().lower())

    for ra in records_a:
        match = None
        for j, rb in enumerate(records_b):
            if j in used_b or rb.get("category") != ra.get("category"):
                continue
            if values_match(ra, rb):
                match = j
                break
        if match is None:
            for j, rb in enumerate(records_b):
                if j in used_b or _match_key(rb) != _match_key(ra):
                    continue
                match = j
                break
        if match is not None:
            used_b.add(match)
            pairs.append({"pair_id": f"p{len(pairs)}", "a": ra, "b": records_b[match]})
        else:
            pairs.append({"pair_id": f"p{len(pairs)}", "a": ra, "b": None})

    for j, rb in enumerate(records_b):
        if j not in used_b:
            pairs.append({"pair_id": f"p{len(pairs)}", "a": None, "b": rb})
    return pairs


def inter_annotator_stats(pairs: list[dict]) -> dict:
    """两标注人值级匹配率（过程质量指标，guideline §3）。

    仅统计 ``values_match`` 判定一致的配对；名称兜底配成对但取值不同的
    不计入 matched（它们正是仲裁要处理的分歧）。
    """
    matched = sum(1 for p in pairs
                  if p["a"] is not None and p["b"] is not None
                  and values_match(p["a"], p["b"]))
    return {"total": len(pairs), "matched": matched,
            "match_rate": round(matched / len(pairs), 4) if pairs else None}


def arbitrate(pairs: list[dict], decisions: list[dict] | None, *, slug: str) -> list[dict]:
    """按仲裁决定合并配对 → 金标记录列表（decisions 缺省取 a 侧）。

    decision 形如 ``{"pair_id": ..., "choice": "a" | "b" | "merged",
    "record": {...}}``；merged 时以人工修正后的 record 为准。
    """
    by_id = {d["pair_id"]: d for d in (decisions or [])}
    gold: list[dict] = []
    for p in pairs:
        d = by_id.get(p["pair_id"], {})
        choice = d.get("choice", "a")
        if choice == "merged" and d.get("record"):
            rec = dict(d["record"])
        else:
            rec = dict(p.get(choice) or p["a"] or p["b"])
        rec.pop("annotator", None)
        rec["source_file"] = slug
        rec["id"] = f"{slug}_gold_{len(gold):03d}"
        gold.append(rec)
    return gold


def save_annotation(slug: str, annotator: str, records: list[dict], out_dir: str) -> str:
    """落盘 ``<out>/<annotator>/<slug>.json``（整体替换）。"""
    return _write_json(Path(out_dir) / annotator / f"{slug}.json", records)


def export_gold(slug: str, gold: list[dict], out_dir: str) -> str:
    """仲裁结果 → ``<out>/gold/<slug>.json``（evaluate_against_gold 直接消费）。"""
    return _write_json(Path(out_dir) / "gold" / f"{slug}.json", gold)


def bucketed_report(records: list[dict], gold: list[dict]) -> dict:
    """金标对照分桶报告（D3）：比单一 P/R 更能指导改进。

    桶判定（每条 gold 取其最优匹配）：
    - ``missed`` 漏抽：无同 category+名称相近的抽取记录；
    - ``value_wrong`` 值错：候选存在但取值不一致；
    - ``unit_wrong`` 单位错：取值一致但单位归一后不同；
    - ``condition_wrong`` 条件归属错：值+单位一致但 temperature/material 不同；
    - ``matched``：完全一致。
    同时给出试点口径（宽松/严格）P/R/F1（复用 evaluate_against_gold，勿另起炉灶）。
    """
    from etl.fulltext_pilot import _name_tokens, evaluate_against_gold

    def _cond(r: dict):
        return (r.get("temperature_K"), str(r.get("material") or "").strip().lower())

    def _unit_key(u):
        return normalize_unit(u) or ""

    buckets = {"matched": [], "missed": [], "value_wrong": [],
               "unit_wrong": [], "condition_wrong": []}
    used: set[int] = set()
    for g in gold:
        tg = _name_tokens(g)
        candidates = [i for i, r in enumerate(records)
                      if i not in used and r.get("category") == g.get("category")
                      and (_name_tokens(r) & tg)]
        best, best_jac = None, 0.0
        for i in candidates:
            jac = len(_name_tokens(records[i]) & tg) / max(len(_name_tokens(records[i]) | tg), 1)
            if jac > best_jac:
                best, best_jac = i, jac
        entry = {"gold_id": g.get("id"), "gold_name": g.get("name_en")}
        if best is None:
            buckets["missed"].append(entry)
            continue
        r = records[best]
        if not values_match(g, r):
            buckets["value_wrong"].append({**entry, "extracted_value": r.get("value"),
                                           "gold_value": g.get("value")})
        elif _unit_key(g.get("unit")) != _unit_key(r.get("unit")):
            buckets["unit_wrong"].append({**entry, "gold_unit": g.get("unit"),
                                          "extracted_unit": r.get("unit")})
        elif _cond(g) != _cond(r):
            buckets["condition_wrong"].append(entry)
        else:
            buckets["matched"].append(entry)
            used.add(best)
    return {
        "counts": {k: len(v) for k, v in buckets.items()},
        "detail": buckets,
        "pilot_metrics": evaluate_against_gold(records, gold),
    }


def _write_json(path: Path, payload: list[dict]) -> str:
    # 绝对路径内嵌 ".." 会被 normpath 折叠而绕过段检查，先显式拒绝
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError(f"Path traversal not allowed: {path}")
    # safe_write_path 拒绝父目录引用段并限制在允许根内（path_safety）
    resolved = safe_write_path(str(path))
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved, payload)
    return resolved


# ---------------------------------------------------------------- Web UI

class RecordsPayload(BaseModel):
    records: list[dict]


class ArbitratePayload(BaseModel):
    a: str
    b: str
    decisions: list[dict]


@dataclass(frozen=True)
class AnnotateSettings:
    source_dir: str = "data/fulltext-pilot/fulltexts"
    out_dir: str = "data/annotation"
    host: str = "127.0.0.1"
    port: int = 8910

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AnnotateSettings":
        import os

        source = os.environ if env is None else env
        return cls(
            source_dir=source.get("NFMD_ANNO_SOURCE_DIR", cls.source_dir),
            out_dir=source.get("NFMD_ANNO_OUT_DIR", cls.out_dir),
            port=int(source.get("NFMD_ANNO_PORT", cls.port)),
        )


def create_app(source_dir: str, out_dir: str) -> FastAPI:
    """构建标注器应用（仅本地使用，绑 127.0.0.1）。"""
    app = FastAPI(title="NFMD annotator", docs_url=None, redoc_url=None)

    def _annotator_path(annotator: str, slug: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", annotator) or ".." in slug:
            raise HTTPException(400, "invalid annotator or slug")
        return Path(out_dir) / annotator / f"{slug}.json"

    @app.get("/api/slugs")
    def slugs():
        root = Path(safe_read_path(source_dir))
        if not root.is_dir():
            raise HTTPException(404, f"source dir not found: {source_dir}")
        files = sorted(p.name for p in root.iterdir()
                       if p.is_file() and p.suffix in (".md", ".txt"))
        return {"slugs": [f[:-len(p.suffix)] for f in files
                          for p in [root / f]]}

    @app.get("/api/fulltext/{slug}")
    def fulltext(slug: str):
        root = Path(safe_read_path(source_dir))
        for ext in (".md", ".txt"):
            candidate = root / f"{slug}{ext}"
            if candidate.is_file():
                with safe_open_read(str(candidate)) as f:
                    return {"slug": slug, "text": f.read()}
        raise HTTPException(404, "fulltext not found")

    @app.get("/api/unit-canonical")
    def unit_canonical(unit: str):
        return {"unit": unit, "canonical": normalize_unit(unit)}

    @app.get("/api/records/{annotator}/{slug}")
    def get_records(annotator: str, slug: str):
        path = _annotator_path(annotator, slug)
        if not path.is_file():
            return {"records": []}
        with safe_open_read(str(path)) as f:
            return {"records": json.load(f)}

    @app.post("/api/records/{annotator}/{slug}")
    def post_records(annotator: str, slug: str, payload: RecordsPayload):
        records = [build_record(f, slug=slug, annotator=annotator, seq=i + 1)
                   for i, f in enumerate(payload.records)]
        issues = [i for r in records for i in check_record(r)
                  if i["severity"] == "error"]
        if issues:
            raise HTTPException(422, detail={"issues": issues})
        path = save_annotation(slug, annotator, records, out_dir)
        return {"saved": len(records), "path": path}

    @app.get("/api/arbitrate/{slug}")
    def get_arbitrate(slug: str, a: str, b: str):
        def _load(annotator: str) -> list[dict]:
            path = _annotator_path(annotator, slug)
            if not path.is_file():
                raise HTTPException(404, f"no annotations from {annotator}")
            with safe_open_read(str(path)) as f:
                return json.load(f)

        pairs = pair_annotations(_load(a), _load(b))
        return {"pairs": pairs, "stats": inter_annotator_stats(pairs)}

    @app.post("/api/arbitrate/{slug}")
    def post_arbitrate(slug: str, payload: ArbitratePayload):
        get = get_arbitrate(slug, payload.a, payload.b)
        gold = arbitrate(get["pairs"], payload.decisions, slug=slug)
        path = export_gold(slug, gold, out_dir)
        return {"gold_count": len(gold), "path": path}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _INDEX_HTML

    return app


_INDEX_HTML = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>NFMD 标注器</title>
<style>
body{font-family:sans-serif;margin:0;display:flex;height:100vh}
#left{flex:1;overflow:auto;padding:1rem;border-right:1px solid #ccc;white-space:pre-wrap}
#right{width:480px;overflow:auto;padding:1rem}
#right label{display:block;font-size:12px;margin-top:6px}
#right input,#right select,#right textarea{width:100%}
.err{color:#c00;font-size:12px;white-space:pre-wrap}
.rec{border:1px solid #ddd;padding:4px;margin:4px 0;font-size:12px}
button{margin-top:8px}
.tabs button.active{font-weight:bold}
</style></head><body>
<div id="left"></div>
<div id="right">
  <div class="tabs">
    <button id="tabAnno" class="active" onclick="showTab('anno')">标注</button>
    <button id="tabArb" onclick="showTab('arb')">仲裁</button>
  </div>
  <div id="paneAnno">
    <label>标注人 <input id="annotator" value="ann1"></label>
    <label>论文 <select id="slug" onchange="loadText()"></select></label>
    <label>划选出处（自动截 2 句）</label>
    <textarea id="srcSentence" rows="3"></textarea>
    <label>出处位置（页/表号） <input id="srcLoc"></label>
    <label>name_en <input id="f_name_en"></label>
    <label>category <select id="f_category">__CATEGORIES__</select></label>
    <label>value_type
      <select id="f_value_type" onchange="renderValueInputs()">
        <option>scalar</option><option>range</option><option>expression</option>
        <option>list</option><option>text</option>
      </select></label>
    <div id="valueInputs"></div>
    <label>unit（原文） <input id="f_unit" oninput="autoCanonical()"></label>
    <label>unit_canonical <input id="f_unit_canonical"></label>
    <label>uncertainty（± 值单独放这里） <input id="f_uncertainty"></label>
    <label>material <input id="f_material"></label>
    <label>temperature_K <input id="f_temperature_K" type="number"></label>
    <label>burnup <input id="f_burnup"></label>
    <label>conditions <input id="f_conditions"></label>
    <label>notes <input id="f_notes"></label>
    <button onclick="addRecord()">暂存本条</button>
    <div id="staged"></div>
    <div id="annoErr" class="err"></div>
    <button onclick="saveAll()">保存全部（校验）</button>
  </div>
  <div id="paneArb" style="display:none">
    <label>论文 <select id="arbSlug" onchange="loadPairs()"></select></label>
    <label>标注人A <input id="arbA" value="ann1"></label>
    <label>标注人B <input id="arbB" value="ann2"></label>
    <div id="arbStats"></div>
    <div id="arbPairs"></div>
    <button onclick="exportGold()">导出 gold</button>
    <div id="arbErr" class="err"></div>
  </div>
</div>
<script>
let staged = [];
document.addEventListener('selectionchange', () => {
  const t = window.getSelection().toString();
  if (t.trim()) document.getElementById('srcSentence').value = t.trim();
});
async function init(){
  const s = await (await fetch('/api/slugs')).json();
  for (const el of ['slug','arbSlug']) {
    const sel = document.getElementById(el);
    sel.innerHTML = s.slugs.map(x => `<option>${x}</option>`).join('');
  }
  loadText();
}
async function loadText(){
  const slug = document.getElementById('slug').value;
  const r = await (await fetch(`/api/fulltext/${slug}`)).json();
  document.getElementById('left').textContent = r.text;
}
function renderValueInputs(){
  const vt = document.getElementById('f_value_type').value;
  const fields = {scalar:['value_scalar (number)'],range:['value_min','value_max'],
    expression:['value_expr'],list:['value_list (JSON array)'],text:['value_str']}[vt];
  document.getElementById('valueInputs').innerHTML =
    fields.map(f => `<label>${f} <input id="f_${f.split(' ')[0]}"></label>`).join('');
}
async function autoCanonical(){
  const u = document.getElementById('f_unit').value;
  if (u) document.getElementById('f_unit_canonical').value =
    (await (await fetch(`/api/unit-canonical?unit=${encodeURIComponent(u)}`)).json()).canonical;
}
function collectForm(){
  const vt = document.getElementById('f_value_type').value;
  const rec = {};
  for (const id of ['name_en','category','unit','unit_canonical','uncertainty',
      'material','temperature_K','burnup','conditions','notes']){
    const v = document.getElementById('f_'+id).value;
    if (v !== '') rec[id] = id === 'temperature_K' ? Number(v) : v;
  }
  for (const f of ['value_scalar','value_min','value_max','value_expr','value_list','value_str']){
    const el = document.getElementById('f_'+f);
    if (el && el.value !== '') rec[f] = (f==='value_scalar'||f==='value_min'||f==='value_max') ? Number(el.value)
      : (f==='value_list' ? JSON.parse(el.value) : el.value);
  }
  rec.value_type = vt;
  rec.source_sentence = document.getElementById('srcSentence').value;
  rec.source_location = document.getElementById('srcLoc').value;
  return rec;
}
function addRecord(){ staged.push(collectForm()); renderStaged(); }
function renderStaged(){
  document.getElementById('staged').innerHTML = staged.map((r,i) =>
    `<div class="rec">${i+1}. ${r.name_en} = ${r.value_scalar ?? r.value_min+'–'+r.value_max ?? r.value_str ?? ''} ${r.unit ?? ''} <button onclick="staged.splice(${i},1);renderStaged()">删</button></div>`).join('');
}
async function saveAll(){
  const slug = document.getElementById('slug').value;
  const ann = document.getElementById('annotator').value;
  const r = await fetch(`/api/records/${ann}/${slug}`, {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({records: staged})});
  document.getElementById('annoErr').textContent = r.ok ? `已保存 ${staged.length} 条` :
    JSON.stringify((await r.json()).detail.issues.map(i=>i.code+': '+i.message), null, 1);
  if (r.ok) staged = [], renderStaged();
}
async function loadPairs(){
  const slug = document.getElementById('arbSlug').value;
  const a = document.getElementById('arbA').value, b = document.getElementById('arbB').value;
  const r = await fetch(`/api/arbitrate/${slug}?a=${a}&b=${b}`);
  const d = await r.json();
  document.getElementById('arbStats').textContent =
    `配对 ${d.stats.total}，值级一致 ${d.stats.matched}，匹配率 ${d.stats.match_rate}`;
  document.getElementById('arbPairs').innerHTML = d.pairs.map(p =>
    `<div class="rec">${p.pair_id}：<br>A: ${fmt(p.a)}<br>B: ${fmt(p.b)}<br>` +
    `<label>裁决 <select id="dec_${p.pair_id}"><option value="a">A</option><option value="b">B</option></select></label></div>`).join('');
  window._pairs = d.pairs;
}
function fmt(r){ return r ? `${r.name_en} = ${JSON.stringify(r.value)} ${r.unit??''}` : '—'; }
async function exportGold(){
  const slug = document.getElementById('arbSlug').value;
  const decisions = window._pairs.map(p => ({pair_id: p.pair_id,
    choice: document.getElementById('dec_'+p.pair_id).value}));
  const r = await fetch(`/api/arbitrate/${slug}`, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({a: document.getElementById('arbA').value,
      b: document.getElementById('arbB').value, decisions})});
  document.getElementById('arbErr').textContent = r.ok ?
    `已导出 ${(await r.json()).gold_count} 条 gold` : await r.text();
}
function showTab(t){
  document.getElementById('paneAnno').style.display = t==='anno' ? '' : 'none';
  document.getElementById('paneArb').style.display = t==='arb' ? '' : 'none';
  document.getElementById('tabAnno').classList.toggle('active', t==='anno');
  document.getElementById('tabArb').classList.toggle('active', t==='arb');
  if (t==='arb') loadPairs();
}
renderValueInputs(); init();
</script></body></html>"""


def _category_options() -> str:
    from etl.rules import VALID_CATEGORIES

    return "".join(f"<option>{c}</option>" for c in sorted(VALID_CATEGORIES))


# 模块导入时填充 category 下拉（零依赖模板的代价：一处字符串替换）
_INDEX_HTML = _INDEX_HTML.replace("__CATEGORIES__", _category_options())


def main() -> int:
    parser = argparse.ArgumentParser(description="人工金标标注器（docs/annotation/guideline.md）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="启动本地 Web UI（默认 127.0.0.1）")
    p_serve.add_argument("--source-dir")
    p_serve.add_argument("--out-dir")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int)

    p_stats = sub.add_parser("stats", help="输出双标注人一致性统计")
    p_stats.add_argument("--slug", required=True)
    p_stats.add_argument("--a", required=True)
    p_stats.add_argument("--b", required=True)
    p_stats.add_argument("--out-dir")

    args = parser.parse_args()
    settings = AnnotateSettings.from_env()
    source_dir = args.source_dir or settings.source_dir
    out_dir = args.out_dir or settings.out_dir

    if args.cmd == "serve":
        import uvicorn

        app = create_app(source_dir, out_dir)
        uvicorn.run(app, host=args.host or settings.host,
                    port=args.port or settings.port)
    else:
        def load(ann: str) -> list[dict]:
            with safe_open_read(str(Path(out_dir) / ann / f"{args.slug}.json")) as f:
                return json.load(f)

        stats = inter_annotator_stats(pair_annotations(load(args.a), load(args.b)))
        print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

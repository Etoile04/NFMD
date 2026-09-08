# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

Layout: **single-context** — one `CONTEXT.md` + `docs/adr/` at the repo root.

> 历史布局共存说明：`docs/superpowers/`（plans、specs）是先前技能族留下的已完成整改记录，只读背景资料，不属于本布局；ADR 与术语表从零开始按需创建。

## Before exploring, read these

- **`CONTEXT.md`** at the repo root
- **`docs/adr/`**: read ADRs that touch the area you're about to work in

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/
│   ├── adr/
│   │   ├── 0001-….md
│   │   └── 0002-….md
│   ├── agents/          ← 本文件与技能配置
│   └── superpowers/     ← 历史整改记录（只读，共存）
├── plans/               ← 设计文档与 DDL
├── scripts/
│   ├── api.py
│   └── etl/
└── sql/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (…), but worth reopening because…_

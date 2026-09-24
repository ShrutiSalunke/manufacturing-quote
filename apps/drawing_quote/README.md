# Drawing Quote (`apps.drawing_quote`)

**North star:** Upload PDF → auto-fill quote → Review / Approve.

Manual parameter entry is a **fallback** when extraction confidence is low — not the primary product flow.

This app is developed on branch `feature/drawing-quote` and is gated by `DRAWING_QUOTE_ENABLED` so it can merge into `main` without activating the feature.

## Constraints

- Families, parameters, extract mappings, and process routing are **client-configurable data** — not hardcoded Python `if family == …` branches.
- Reuse existing `Quote` / `Process` calculate and Issue PDF flows; do not fork the costing engine.
- Extractors (PDF text, PDF vision/LLM, DXF) are **pluggable** behind a registry.

## Feature flag

```env
DRAWING_QUOTE_ENABLED=False
```

Set `True` to expose URLs and the sidebar link.

Optional (later phases):

```env
DRAWING_QUOTE_VISION_PROVIDER=none
DRAWING_QUOTE_VISION_API_KEY=
DRAWING_QUOTE_VISION_MODEL=
```

## Phases

| Phase | Status | Outcome |
|-------|--------|---------|
| **P0** | Done (this scaffold) | App, flag, placeholder route |
| **P1** | Pending | PartFamily models + admin/UI |
| **P2** | Pending | Assemble Quote from family + params |
| **P3** | Pending | PDF upload + extract pipeline (core) |
| **P4** | Pending | Review / Approve UX |
| **P5** | Pending | Seed families 1–13 |
| **P6** | Pending | DXF metrics extractor |
| **P7** | Pending | Tests, harden, merge readiness |

## Smoke test (P0)

1. Set `DRAWING_QUOTE_ENABLED=True` in `.env`.
2. Restart `runserver`.
3. Sign in → sidebar **Quoting → Quote from drawing**.
4. Page should load without errors.
5. Set flag back to `False` → nav link and `/drawing-quote/` routes disappear; rest of app unchanged.

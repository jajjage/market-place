# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`docs/README.md`** — Read the Project Master Index to navigate to the feature-specific sub-documents under the `docs/` directory before starting any task.
- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists.
- **`docs/adr/`** — Read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CONTEXT.md
├── AGENTS.md
├── docs/
│   ├── README.md
│   ├── backend/
│   │   ├── architecture.md
│   │   ├── elasticsearch.md
│   │   └── celery.md
│   ├── frontend/
│   │   └── landing-spec.md
│   ├── guidelines/
│   │   └── best-practices.md
│   └── adr/
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md` and the master docs. Don't drift to synonyms the glossary explicitly avoids.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding.

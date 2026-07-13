---
name: read-docs
description: Instructs the agent to consult the central project documentation index and relevant sub-documents before starting work.
disable-model-invocation: true
---

# Read Project Docs Wayfinding

Before executing any implementation, research, or troubleshooting steps, follow this wayfinding process.

## Process

### 1. Consult the Master Index
- Open and read [docs/README.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/README.md).
- Identify which sub-document in the Documentation Registry corresponds to the current feature or area of work.

### 2. Read the Specific Sub-Doc
- Open the identified sub-document (e.g., [docs/backend/architecture.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/backend/architecture.md) or [docs/research/nigerian_escrow_mvp_roadmap.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/research/nigerian_escrow_mvp_roadmap.md)).
- Extract key requirements, structural constraints, design patterns, and context before modifying the codebase.
- **Do not make assumptions** about settings, parameters, or database schemas that are outlined in the documentation.

### 3. Implement & Execute
- Perform the requested task following the constraints defined in the sub-document.

### 4. Update the Documentation
- **Important**: Once your code changes are complete, update the relevant sub-document under `docs/` with any new APIs, configuration options, models, or design choices introduced.
- If your work created a new module or feature area without an existing sub-document, create a new `.md` file under the appropriate `docs/` subdirectory and add it to the registry inside `docs/README.md`.

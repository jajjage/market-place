# SafeTrade Project Documentation Master Index

Welcome to the central documentation workspace for SafeTrade. This repository uses a modular, agent-friendly documentation layout. 

> [!IMPORTANT]
> **Wayfinding Rules for AI Agents:**
> Before initiating any code modifications or research tasks, you MUST:
> 1. Read this index to locate the sub-document relevant to your task.
> 2. Read the identified sub-document fully to understand the current design constraints, specs, and integration points.
> 3. Perform your implementation.
> 4. **Iterate & Expand:** If your work adds new modules, settings, or modifies existing contracts, you must update the corresponding sub-document to reflect the changes. If no sub-document exists for your feature, create a new one under the appropriate directory and register it in this Index.

---

## Documentation Registry

### 1. Guidelines & Standards
*   [docs/guidelines/best-practices.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/guidelines/best-practices.md)
    *   *Purpose:* Coding standards, style rules (PEP 8), testing strategies, and architecture patterns (Service Layer, Repository).

### 2. Backend Specifications
*   [docs/backend/architecture.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/backend/architecture.md)
    *   *Purpose:* System layout, technology stack, database schemas, and application design patterns (DDD, CQRS).
*   [docs/backend/elasticsearch.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/backend/elasticsearch.md)
    *   *Purpose:* Elasticsearch index mapping, indexing workflow, and custom edge-ngram analyzer configurations.
*   [docs/backend/celery.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/backend/celery.md)
    *   *Purpose:* Celery worker settings, queue configurations (high/medium/low priority routing), and production deployment scripts.
*   [docs/backend/kibana-setup.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/backend/kibana-setup.md)
    *   *Purpose:* Kibana dashboard setup, data views creation, and search metrics configuration.

### 3. Frontend Specifications
*   [docs/frontend/landing-spec.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/frontend/landing-spec.md)
    *   *Purpose:* UI layout specifications, landing page structure, design system tokens, and performance optimizations. Contains details about the cached product list retrieval.

### 4. Market Research & MVP Roadmaps
*   [docs/research/nigerian_escrow_mvp_roadmap.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/research/nigerian_escrow_mvp_roadmap.md)
    *   *Purpose:* Analysis of global escrow leaders (eBay, Etsy, Mercari), trust gap mitigation in the Nigerian e-commerce market, and codebase gap analysis for payment/KYC integrations.

### 5. Architectural Decision Records (ADRs)
*   [docs/adr/0001-consolidate-search-in-products-app.md](file:///c:/Users/musta/fasu-marketplace/market-place/docs/adr/0001-consolidate-search-in-products-app.md)
    *   *Purpose:* Decision to keep all search views, endpoints, and Elasticsearch index document mappings inside the products app and remove the empty search app.

---

## Monorepo & Deployment Layout
*   [docker-compose.yml](file:///c:/Users/musta/fasu-marketplace/market-place/docker-compose.yml): The multi-service local environment definition (Django, Redis, DB, Celery Workers, Beat, Flower).
*   [.agents/](file:///c:/Users/musta/fasu-marketplace/market-place/.agents/): Custom agent guidelines and skill directories.

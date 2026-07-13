# Backend Design & Architecture Specification

## 1. Overview
This document outlines the backend architecture and design patterns for the escrow-based marketplace platform. It facilitates secure transactions between buyers and sellers, providing trust in social commerce transactions. The platform handles user management, product listings, escrow payments, order fulfillment, and logistics integration.

---

## 2. System Architecture

### 2.1 High-Level Architecture
The backend follows a microservices / domain-modular architecture with the following core modules:
- **User Module**: Manages authentication, authorization, profiles, and address book.
- **Product Module**: Handles product listings, categories, variant options, inventory, and search indexes.
- **Transaction Module**: Manages escrow payments, payouts, timeouts, and state transitions.
- **Dispute Module**: Handles buyer-seller disputes, mediation comments, and resolution states.
- **Messaging Module**: Facilitates websocket-based real-time communication.
- **Notification Module**: Handles push, email, and SMS triggers.

### 2.2 Domain Organization
All services are organized in `apps/` with clean separation of layers:
- `api/`: Views, ViewSets, routers, and Serializers.
- `models/`: Models, managers, and QuerySets.
- `services/`: Encapsulates transaction state-transitions, listing caches, and business calculations.
- `tasks/`: Asynchronous celery jobs (e.g. timeout triggers, cache cleanups).
- `signals/`: Model triggers for invalidations.

---

## 3. Technology Stack & Core Technologies
- **Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL (relational storage)
- **Caching**: Redis (caching and sessions)
- **Task Queue**: Celery (async background tasks)
- **Search**: Elasticsearch (product search DSL)
- **Authentication**: JWT (JSON Web Tokens)
- **Containerization**: Docker (local compose environment)

---

## 4. Key Business Logic Components

### 4.1 Escrow Payment Flow
1. Buyer places an order and pays (monies held on gateway).
2. Platform transitions status to `payment_received`.
3. Seller is notified and ships the product.
4. Buyer confirms receipt or the inspection timeout expires.
5. Platform transitions status to `completed` and transfers funds to the seller.
6. If an issue is reported, a `Dispute` is opened, pausing all timers.

### 4.2 Application Layer Design Patterns
- **Repository / QuerySet Seams**: Custom querysets on model managers for optimized prefetching and filtering.
- **Service Layer Pattern**: All core workflows (such as escrow transitions and caching) live inside service classes, shielding views from database queries.
- **State Machine Pattern**: Transaction states are strictly validated during transit inside the transition service.

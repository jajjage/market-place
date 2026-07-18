# SafeTrade Domain Context

Welcome to the central glossary for the SafeTrade marketplace.

## Language

**Product Document**:
The search engine representation of a Product, optimized for fast full-text, faceted, and autocomplete search.
_Avoid_: Product index entry

**Search Log**:
An analytical record of a unique search query executed by a user, tracking the query text, filters, results returned, and system latency.
_Avoid_: Query log, search trace

**Popular Search**:
An aggregated counter tracking how often a specific query has been searched to facilitate trending term recommendations.
_Avoid_: Trending search

**Seller Payment Profile**:
A user's payment and banking credentials (e.g., bank account number, bank code, and account name) along with gateway-specific identifiers (subaccount ID / recipient code), isolated from their general user profile.
_Avoid_: User payment details

**Fund Hold**:
A temporary restriction placed on a portion of a seller's funds. It supports concurrent, independent hold records with different scopes (e.g., standard transaction hold, active dispute hold, or account risk reserve).
_Avoid_: Frozen balance, transaction block

**Seller Balance Ledger**:
A double-entry accounting log tracking credits and debits (sales, payout releases, fees, and chargebacks) for a seller. It maintains their running balance and supports negative balances.
_Avoid_: Payout log

**Pluggable KYC Service**:
An abstract identity verification wrapper that resolves a seller's national identity documents (BVN/NIN) using togglable providers (such as mock or live Paystack/Smile ID API integrations).
_Avoid_: Identity checker

**Post-Release Dispute**:
A dispute or bank chargeback initiated after the escrow funds have already been released to the seller, resulting in a debit ledger adjustment that can make the seller's balance negative.
_Avoid_: Late refund


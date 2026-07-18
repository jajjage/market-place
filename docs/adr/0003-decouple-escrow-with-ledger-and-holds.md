# 0003-decouple-escrow-with-ledger-and-holds

We decided to decouple transaction state from funds holding by introducing a `FundHold` model and a double-entry `SellerBalanceLedger` instead of relying solely on the single `EscrowTransaction.status` field. This allows the platform to manage concurrent holds (e.g., standard transaction hold, active dispute, or account risk reserve) and supports negative seller balances from post-release chargebacks/disputes, protecting the platform from direct financial loss.

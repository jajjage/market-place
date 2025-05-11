# Escrow Platform: User Transition Permissions

This document outlines the allowed state transitions for each user role in the escrow platform.

## Role-Based Transition Permissions

### BUYER Permissions
When a user is a BUYER, they can make the following transitions:

| Current State | Can Transition To | Notes |
|---------------|-------------------|-------|
| `initiated` | `cancelled` | Buyer can cancel the transaction after it's initiated |
| `payment_received` | *none* | Buyer cannot transition from this state |
| `shipped` | `delivered` | Buyer confirms delivery of the item |
| `delivered` | `inspection` | Buyer can start the inspection period |
| `inspection` | `completed`, `disputed` | Buyer can either complete the transaction or open a dispute |
| `disputed` | *none* | Buyer cannot transition from this state (admin handles disputes) |
| `completed` | *none* | Buyer cannot transition from this state (waiting for fund release) |
| `funds_released` | *none* | Final state - no transitions possible |
| `refunded` | *none* | Final state - no transitions possible |
| `cancelled` | *none* | Final state - no transitions possible |

### SELLER Permissions
When a user is a SELLER, they can make the following transitions:

| Current State | Can Transition To | Notes |
|---------------|-------------------|-------|
| `initiated` | `payment_received`, `cancelled` | Seller can confirm payment or cancel the transaction |
| `payment_received` | `shipped` | Seller confirms item has been shipped |
| `shipped` | *none* | Seller cannot transition from this state (waiting for buyer) |
| `delivered` | *none* | Seller cannot transition from this state (waiting for buyer) |
| `inspection` | *none* | Seller cannot transition from this state (waiting for buyer) |
| `disputed` | *none* | Seller cannot transition from this state (admin handles disputes) |
| `completed` | `funds_released` | Seller confirms fund withdrawal from escrow |
| `funds_released` | *none* | Final state - no transitions possible |
| `refunded` | *none* | Final state - no transitions possible |
| `cancelled` | *none* | Final state - no transitions possible |

### ADMIN Permissions (implied from the structure)
While not explicitly shown in your provided code, it appears that ADMIN users would handle disputes and potentially have additional permissions.

## Transaction Flow Visualization

```
[initiated] → (Seller) → [payment_received] → (Seller) → [shipped] → (Buyer) → [delivered] 
    ↑                                                                    ↓
    |                                                                    |
(Buyer/Seller)                                                     (Buyer)
    |                                                                    |
    |                                                                    ↓
[cancelled] ← - - - - - - - - - - - - - - - - - - - - - - - - [inspection]
                                                                    ↓
                                                               (Buyer)
                                                                    |
                                                              ┌─────┴─────┐
                                                              ↓           ↓
                                                      [completed]    [disputed]
                                                          ↓          (Admin)
                                                      (Seller)           |
                                                          ↓        ┌─────┴─────┐
                                                  [funds_released] ↓           ↓
                                                      Final    [completed]  [refunded]
                                                                    ↓          Final
                                                               (Seller)
                                                                    ↓
                                                            [funds_released]
                                                                 Final
```

## Implementation Notes

This permission structure ensures:
1. Clear separation of responsibilities between buyer and seller
2. A linear transaction flow with appropriate checks and balances
3. Final states that cannot be transitioned out of
4. Appropriate intervention points for administrators (disputes)
5. Proper fund management through escrow until explicit release

### Fund Flow Management

- **Funds in Escrow**: When the state is `payment_received`, the funds are held in escrow and not transferred to the seller
- **Inspection Period**: Buyer has time to inspect the item during the `inspection` state
- **Completion**: When buyer marks the transaction as `completed`, it indicates approval but funds remain in escrow
- **Fund Release**: The seller must explicitly confirm fund withdrawal via the `funds_released` state to complete the monetary aspect of the transaction

This two-step completion process provides additional security and clarity regarding when funds are actually transferred to the seller's account.

The code implementation uses conditional variables (`is_buyer`, `is_seller`) to dynamically determine available transitions based on the user's role in the specific transaction.
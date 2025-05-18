# Transaction Endpoints Documentation

## Base Endpoints

### List Transactions
- **URL:** `/api/transactions/`
- **Method:** GET
- **Description:** List transactions with filtering and pagination
- **Access:** BUYER/SELLER (filtered to their own transactions)
- **Filters:**
  - `status`: Filter by transaction status
  - `created_after`: DateTime filter
  - `created_before`: DateTime filter
  - `search`: Search across tracking_id, product title, buyer/seller email
- **Ordering:** created_at, updated_at, status, amount

### Get Single Transaction
- **URL:** `/api/transactions/{id}/`
- **Method:** GET
- **Description:** Get detailed information about a specific transaction
- **Access:** Transaction buyer/seller only

## Buyer Endpoints

### My Purchases
- **URL:** `/api/transactions/my-purchases/`
- **Method:** GET
- **Permission:** BUYER only
- **Description:** List all purchases for current buyer
- **Filters:**
  - `status`: Filter by transaction status
- **Response:** List of transactions with basic details

## Seller Endpoints

### My Sales
- **URL:** `/api/transactions/my-sales/`
- **Method:** GET
- **Permission:** SELLER only
- **Description:** List all sales for current seller
- **Filters:**
  - `status`: Filter by transaction status
- **Response:** List of transactions with basic details

## Transaction Management

### Update Transaction Status
- **URL:** `/api/transactions/{id}/update-status/`
- **Method:** POST
- **Permission:** Varies by status change
- **Request Body:**
  ```json
  {
    "status": "string (required)",
    "notes": "string",
    "tracking_number": "string (for shipping)",
    "shipping_carrier": "string (for shipping)"
  }
  ```
- **Allowed Status Changes:**
  - **Buyer can change to:**
    - initiated → cancelled
    - shipped → delivered
    - delivered → inspection
    - inspection → completed/disputed
  - **Seller can change to:**
    - initiated → cancelled
    - payment_received → shipped
    - completed → funds_released

### Track Transaction
- **URL:** `/api/transactions/track/{tracking_id}/`
- **Method:** GET
- **Permission:** Transaction buyer/seller only
- **Description:** Get detailed tracking information
- **Response:**
  ```json
  {
    "transaction_details": "object",
    "history": "array of status changes",
    "product_details": "object",
    "shipping_info": {
      "tracking_number": "string",
      "shipping_carrier": "string",
      "status_updates": "array"
    }
  }
  ```

## Dispute Management

### List Disputes
- **URL:** `/api/disputes/`
- **Method:** GET
- **Permission:** BUYER/SELLER
- **Description:** List disputes related to user's transactions

### Create Dispute
- **URL:** `/api/disputes/`
- **Method:** POST
- **Permission:** BUYER only
- **Request Body:**
  ```json
  {
    "transaction": "id",
    "reason": "string (required)",
    "description": "string (required)",
    "evidence_files": "array of files"
  }
  ```

### Update Dispute
- **URL:** `/api/disputes/{id}/`
- **Method:** PUT/PATCH
- **Permission:** Original dispute creator
- **Request Body:** Same as Create Dispute

## Payment Integration

### Get Payment Configuration
- **URL:** `/api/transactions/payment-config/`
- **Method:** GET
- **Description:** Get payment configuration for transaction

### Verify Payment
- **URL:** `/api/transactions/verify-payment/`
- **Method:** POST
- **Description:** Verify payment status for transaction

### Payment Webhook
- **URL:** `/api/transactions/flutterwave-webhook/`
- **Method:** POST
- **Description:** Handle payment gateway webhook notifications
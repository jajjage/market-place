# API Documentation for Rating Endpoints

This document describes the endpoints for the `RatingViewSet` in the comments app, including the expected request and response data for each endpoint.

---

## 1. Create Rating

- **Endpoint:** `POST /api/comments/ratings/`
- **Description:** Create a rating for a completed transaction.
- **Request Body:**
  ```json
  {
    "rating": 1-5 (integer, required),
    "comment": "string (optional)",
    "transaction_id": "uuid (required if not in query)"
  }
  ```
- **Response:**
  ```json
  {
    "id": int,
    "rating": int,
    "comment": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "is_verified": bool,
    "from_user": {...},
    "to_user": {...},
    "transaction_title": "string",
    "transaction_date": "datetime"
  }
  ```

---

## 2. List Ratings (Received)

- **Endpoint:** `GET /api/comments/ratings/`
- **Description:** List ratings received by the authenticated user.
- **Response:**
  ```json
  [
    {
      "id": int,
      "rating": int,
      "comment": "string",
      "created_at": "datetime",
      "is_verified": bool,
      "from_user_name": "string",
      "transaction_title": "string"
    },
    ...
  ]
  ```

---

## 3. Retrieve Rating Detail

- **Endpoint:** `GET /api/comments/ratings/{id}/`
- **Description:** Get details of a specific rating.
- **Response:** Same as Create Rating response.

---

## 4. Check Rating Eligibility

- **Endpoint:** `GET /api/comments/ratings/eligibility/?seller_id={uuid}`
- **Endpoint:** `GET /api/comments/ratings/eligibility/?transaction_id={uuid}`
- **Description:** Check if the user can rate a seller or a transaction.
- **Response (seller_id):**
  ```json
  {
    "can_rate": bool,
    "reason": "string",
    "rateable_transactions": [
      {
        "transaction_id": "uuid",
        "transaction_title": "string",
        "transaction_amount": "string",
        "status_changed_at": "datetime",
        "rating_deadline": "datetime",
        "days_remaining": int
      }
    ],
    "total_completed_transactions": int,
    "seller_name": "string",
    "seller_id": "uuid"
  }
  ```
- **Response (transaction_id):**
  ```json
  {
    "can_rate": bool,
    "reason": "string",
    "expires_at": "datetime|null",
    "transaction_id": "uuid",
    "seller_name": "string|null"
  }
  ```

---

## 5. Get Rating Stats

- **Endpoint:** `GET /api/comments/ratings/stats/?user_id={int}`
- **Description:** Get aggregated rating statistics for a user.
- **Response:**
  ```json
  {
    "average_rating": "decimal",
    "total_ratings": int,
    "rating_distribution": {"1": int, "2": int, ...},
    "recent_ratings_count": int
  }
  ```

---

## 6. List Pending Ratings

- **Endpoint:** `GET /api/comments/ratings/pending/?limit={int}`
- **Description:** List transactions where the user can still provide ratings.
- **Response:**
  ```json
  [
    {
      "transaction_id": int,
      "transaction_title": "string",
      "seller_name": "string",
      "status_changed_at": "datetime",
      "expires_at": "datetime",
      "days_remaining": int
    },
    ...
  ]
  ```

---

## 7. List Ratings Given

- **Endpoint:** `GET /api/comments/ratings/given/`
- **Description:** List ratings given by the authenticated user.
- **Response:** Same as Retrieve Rating Detail (list).

---

## 8. List Ratings Received

- **Endpoint:** `GET /api/comments/ratings/received/`
- **Description:** List ratings received by the authenticated user.
- **Response:** Same as Retrieve Rating Detail (list).

---

## 9. List Ratings for a Specific User

- **Endpoint:** `GET /api/comments/ratings/user/{user_id}/`
- **Description:** List ratings received by a specific user.
- **Response:** Same as List Ratings (Received).

---

**Note:** All endpoints require authentication via Knox Token.

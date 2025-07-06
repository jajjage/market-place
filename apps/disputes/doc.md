# Disputes API

This document outlines the API endpoints for managing disputes.

## Endpoints

### `POST /api/v1/disputes/`

-   **Description:** Creates a new dispute for a transaction.
-   **Authentication:** Required.
-   **Permissions:** Only the buyer or seller of the transaction can create a dispute.
-   **Data:**
    -   `transaction_id` (string, required): The UUID of the transaction to dispute.
    -   `reason` (string, required): The reason for the dispute. Must be one of the following: `not_as_described`, `not_received`, `damaged`, `wrong_item`, `other`.
    -   `description` (string, required): A detailed description of the dispute.
-   **Success Response:**
    -   **Code:** 201 CREATED
    -   **Content:** A `DisputeDetailSerializer` representation of the newly created dispute.
-   **Error Responses:**
    -   **Code:** 400 BAD REQUEST - If the request data is invalid.
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.
    -   **Code:** 403 FORBIDDEN - If the user is not the buyer or seller of the transaction.
    -   **Code:** 404 NOT FOUND - If the transaction does not exist.

### `GET /api/v1/disputes/`

-   **Description:** Retrieves a list of disputes.
-   **Authentication:** Required.
-   **Permissions:** Staff users can see all disputes. Regular users can only see disputes related to their own transactions.
-   **Query Parameters:**
    -   `status` (string, optional): Filter disputes by status.
-   **Success Response:**
    -   **Code:** 200 OK
    -   **Content:** A list of `DisputeListSerializer` representations of the disputes.
-   **Error Responses:**
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.

### `GET /api/v1/disputes/{id}/`

-   **Description:** Retrieves the details of a specific dispute.
-   **Authentication:** Required.
-   **Permissions:** Staff users can see all disputes. Regular users can only see disputes related to their own transactions.
-   **Success Response:**
    -   **Code:** 200 OK
    -   **Content:** A `DisputeDetailSerializer` representation of the dispute.
-   **Error Responses:**
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.
    -   **Code:** 404 NOT FOUND - If the dispute does not exist.

### `POST /api/v1/disputes/{id}/resolve/`

-   **Description:** Resolves a dispute.
-   **Authentication:** Required.
-   **Permissions:** Only staff users can resolve disputes.
-   **Data:**
    -   `status` (string, required): The new status of the dispute. Must be one of the following: `resolved_buyer`, `resolved_seller`, `closed`.
    -   `resolution_note` (string, optional): A note explaining the resolution.
-   **Success Response:**
    -   **Code:** 200 OK
    -   **Content:** A `DisputeDetailSerializer` representation of the resolved dispute.
-   **Error Responses:**
    -   **Code:** 400 BAD REQUEST - If the request data is invalid.
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.
    -   **Code:** 403 FORBIDDEN - If the user is not a staff member.
    -   **Code:** 404 NOT FOUND - If the dispute does not exist.

### `GET /api/v1/disputes/my/`

-   **Description:** Retrieves a list of disputes for the currently authenticated user.
-   **Authentication:** Required.
-   **Query Parameters:**
    -   `status` (string, optional): Filter disputes by status.
-   **Success Response:**
    -   **Code:** 200 OK
    -   **Content:** A list of `DisputeListSerializer` representations of the disputes.
-   **Error Responses:**
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.

### `GET /api/v1/disputes/stats/`

-   **Description:** Retrieves statistics about disputes.
-   **Authentication:** Required.
-   **Permissions:** Only staff users can view dispute statistics.
-   **Success Response:**
    -   **Code:** 200 OK
    -   **Content:** An object containing dispute statistics.
-   **Error Responses:**
    -   **Code:** 401 UNAUTHORIZED - If the user is not authenticated.
    -   **Code:** 403 FORBIDDEN - If the user is not a staff member.

# Traditional Authentication API

This document outlines the API endpoints for traditional email/password authentication.

## Endpoints

### 1. User Login

- **Endpoint:** `/auth/traditional/login/`
- **Method:** `POST`
- **Description:** Authenticates a user with their email and password. On success, it returns an access and refresh token pair, both in the response body and as HTTP-only cookies (`access_token` and `refresh_token`).
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "your_password"
  }
  ```
- **Successful Response (200 OK):**
  ```json
  {
    "status": "success",
    "message": "Login successful",
    "data": {
      "access": "your_access_token",
      "refresh": "your_refresh_token",
      "user_id": "user_id",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe"
    }
  }
  ```
- **Dependencies:** None.

### 2. Refresh Access Token

- **Endpoint:** `/auth/traditional/token/refresh/`
- **Method:** `POST`
- **Description:** Renews an expired access token using a valid refresh token. The refresh token must be sent in an HTTP-only cookie named `refresh_token`.
- **Request Body:** None (relies on the `refresh_token` cookie).
- **Successful Response (200 OK):** A new access token is returned in the response and set as a new `access_token` cookie.
- **Dependencies:** A valid `refresh_token` cookie obtained from the login endpoint.

### 3. Verify Access Token

- **Endpoint:** `/auth/traditional/token/verify/`
- **Method:** `POST`
- **Description:** Checks if an access token is valid. The access token is expected in an HTTP-only cookie named `access_token`.
- **Request Body:** None (relies on the `access_token` cookie).
- **Successful Response (200 OK):**
  ```json
  {}
  ```
- **Dependencies:** A valid `access_token` cookie.

### 4. User Logout

- **Endpoint:** `/auth/traditional/logout/`
- **Method:** `POST`
- **Description:** Logs the user out by clearing the `access_token` and `refresh_token` cookies.
- **Request Body:** None.
- **Successful Response (200 OK):**
  ```json
  {
    "message": "Successfully logged out."
  }
  ```
- **Dependencies:** The user must be logged in (i.e., have valid token cookies).

### 5. Test Authentication

- **Endpoint:** `/auth/traditional/test/`
- **Method:** `GET`
- **Description:** A simple endpoint to verify if the user is currently authenticated.
- **Request Body:** None.
- **Successful Response (200 OK):**
  ```json
  {
    "message": "You are authenticated"
  }
  ```
- **Dependencies:** A valid `access_token` cookie.

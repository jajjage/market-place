# Google Authentication API

This document outlines the API endpoint for Google OAuth2 authentication.

## Endpoints

### 1. Google Authentication

- **Endpoint:** `/auth/google/`
- **Method:** `POST`
- **Description:** Authenticates a user with a Google OAuth2 access token. If the user doesn't exist, a new account is created using the information from their Google profile. On success, it returns access and refresh tokens, both in the response body and as HTTP-only cookies (`access_token` and `refresh_token`).
- **Request Body:**
  ```json
  {
    "access_token": "google_oauth2_access_token"
  }
  ```
- **Successful Response (201 Created):**
  ```json
  {
    "status": "success",
    "message": "Social authentication successful",
    "data": {
      "id": "user_id",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "verification_status": "Email Verified",
      "profile": {
        "id": "profile_id",
        "display_name": "JohnD",
        "bio": "A short bio.",
        "phone_number": "+1234567890",
        "country": "USA",
        "city": "New York",
        "email_verified": true,
        "phone_verified": false,
        "avatar_url": "http://example.com/avatar.jpg"
      }
    }
  }
  ```
- **Dependencies:** The client application must first obtain an OAuth2 access token from Google.

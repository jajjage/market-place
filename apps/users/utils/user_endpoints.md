# User Endpoints Documentation

## Authentication Endpoints

### Login
- **URL:** `/api/auth/token/`
- **Method:** POST
- **Description:** Obtain JWT tokens (sets in cookies)
- **Request Body:**
  ```json
  {
    "email": "string",
    "password": "string"
  }
  ```

### Refresh Token
- **URL:** `/api/auth/token/refresh/`
- **Method:** POST
- **Description:** Refresh JWT token using refresh token

### Verify Token
- **URL:** `/api/auth/token/verify/`
- **Method:** POST
- **Description:** Verify JWT token validity

### Logout
- **URL:** `/api/auth/logout/`
- **Method:** POST
- **Description:** Logout user and clear auth cookies

## User Profile Endpoints

### Get Current User Profile
- **URL:** `/api/users/profiles/me/`
- **Method:** GET
- **Description:** Get current user's full profile
- **Access:** Authenticated user

### Get Public User Profile
- **URL:** `/api/users/profiles/{id}/`
- **Method:** GET
- **Description:** Get public profile of any user
- **Access:** Authenticated users

## User Store Endpoints

### List Stores
- **URL:** `/api/users/store/`
- **Method:** GET
- **Description:** List stores (filtered by permissions)
- **Access:** SELLER only

### Create Store
- **URL:** `/api/users/store/`
- **Method:** POST
- **Permission:** SELLER only
- **Request Body:**
  ```json
  {
    "name": "string (required)",
    "description": "string",
    "return_policy": "string",
    "shipping_policy": "string",
    "website": "string",
    "is_active": "boolean"
  }
  ```

### Update Store
- **URL:** `/api/users/store/{id}/`
- **Method:** PUT/PATCH
- **Permission:** Store owner only
- **Request Body:** Same as Create Store

## User Rating Endpoints

### List Ratings
- **URL:** `/api/users/ratings/`
- **Method:** GET
- **Description:** List ratings (given/received)
- **Access:** Authenticated user

### Create Rating
- **URL:** `/api/users/ratings/`
- **Method:** POST
- **Permission:** Authenticated user
- **Request Body:**
  ```json
  {
    "to_user": "integer (required)",
    "transaction": "integer (required)",
    "rating": "integer (1-5) (required)",
    "comment": "string"
  }
  ```

### Update Rating
- **URL:** `/api/users/ratings/{id}/`
- **Method:** PUT/PATCH
- **Permission:** Rating creator only
- **Request Body:** Same as Create Rating

## User Address Endpoints

### List Addresses
- **URL:** `/api/users/addresses/`
- **Method:** GET
- **Description:** List user's addresses
- **Access:** Address owner only

### Create Address
- **URL:** `/api/users/addresses/`
- **Method:** POST
- **Permission:** Authenticated user
- **Request Body:**
  ```json
  {
    "name": "string (required)",
    "street_address": "string (required)",
    "city": "string (required)",
    "state": "string (required)",
    "country": "string (required)",
    "postal_code": "string (required)",
    "phone": "string",
    "is_default": "boolean"
  }
  ```

### Update Address
- **URL:** `/api/users/addresses/{id}/`
- **Method:** PUT/PATCH
- **Permission:** Address owner only
- **Request Body:** Same as Create Address

## Social Authentication

### Social Auth Provider
- **URL:** `/api/auth/o/{provider}/`
- **Method:** POST
- **Description:** Authenticate with social provider
- **Supported Providers:** Google, Facebook, Apple
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.products.product_negotiation.views import ProductNegotiationViewSet

router = DefaultRouter()
router.register(r"negotiations", ProductNegotiationViewSet, basename="negotiation")

urlpatterns = [
    path("", include(router.urls)),
]

"""
This configuration provides the following endpoints:

Core Negotiation Endpoints:
1. POST /products/{product_id}/initiate-negotiation/
   - Initiate a new negotiation for a product
   - Body: {"offered_price": 150.00, "notes": "Optional notes"}

2. POST /negotiations/respond/{negotiation_id}/
   - Seller responds to buyer's offer
   - Body: {"response_type": "accept|reject|counter", "counter_price": 175.00, "notes": "Optional"}

3. POST /negotiations/buyer-respond/{negotiation_id}/
   - Buyer responds to seller's counter offer
   - Body: {"response_type": "accept|reject|counter", "counter_price": 160.00}

4. POST /negotiations/create-transaction/{negotiation_id}/
   - Create escrow transaction from accepted negotiation
   - Body: {"quantity": 1, "notes": "Transaction notes"}

User Management Endpoints:
5. GET /negotiations/my-negotiations/
   - Get current user's negotiations
   - Query params: ?status=pending&role=buyer&product_id=123

6. GET /negotiations/my-history/
   - Get user's negotiation history
   - Query params: ?limit=50

7. POST /negotiations/cancel/{negotiation_id}/
   - Cancel an active negotiation

Analytics Endpoints:
8. GET /negotiations/stats/{product_id}/
   - Get negotiation statistics for a product (product owner only)

Standard REST Endpoints:
9. GET /negotiations/
   - List user's negotiations (filtered by permissions)

10. GET /negotiations/{negotiation_id}/
    - Get specific negotiation details

Usage Examples:

# Initiate negotiation
POST /products/123/initiate-negotiation/
{
    "offered_price": 150.00,
    "notes": "Would you consider this price?"
}

# Seller accepts offer
POST /negotiations/respond/456/
{
    "response_type": "accept",
    "notes": "Accepted! Thank you."
}

# Seller makes counter offer
POST /negotiations/respond/456/
{
    "response_type": "counter",
    "counter_price": 175.00,
    "notes": "How about this price?"
}

# Buyer accepts counter offer
POST /negotiations/buyer-respond/456/
{
    "response_type": "accept"
}

# Create transaction from accepted negotiation
POST /negotiations/create-transaction/456/
{
    "quantity": 1,
    "notes": "Looking forward to the purchase!"
}

# Get my negotiations with filters
GET /negotiations/my-negotiations/?status=pending&role=seller

# Get negotiation stats (product owner only)
GET /negotiations/stats/123/
"""

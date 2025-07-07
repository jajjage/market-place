# Negotiation Feature Settings
NEGOTIATION_SETTINGS = {
    # Business Rules
    "MAX_CONCURRENT_NEGOTIATIONS": 5,  # Max active negotiations per user
    "MAX_NEGOTIATION_ROUNDS": 5,  # Max back-and-forth rounds
    "DEFAULT_NEGOTIATION_DEADLINE_HOURS": 72,  # Default 3 days
    "MIN_OFFER_PERCENTAGE": 30,  # Minimum 30% of original price
    "AUTO_EXPIRE_HOURS": 168,  # Auto-expire after 7 days
    # Rate Limiting
    "HOURLY_NEGOTIATION_LIMIT": 20,
    "DAILY_NEGOTIATION_LIMIT": 50,
    "SPAM_DETECTION_THRESHOLD": 10,  # Same user, same product
    # Caching
    "CACHE_TIMEOUT_SHORT": 300,  # 5 minutes
    "CACHE_TIMEOUT_MEDIUM": 1800,  # 30 minutes
    "CACHE_TIMEOUT_LONG": 3600,  # 1 hour
    # Notifications
    "NOTIFY_SELLER_NEW_OFFER": True,
    "NOTIFY_BUYER_RESPONSE": True,
    "NOTIFY_EXPIRATION_WARNING": True,
    "EXPIRATION_WARNING_HOURS": 24,  # Warn 24 hours before expiry
    # Analytics
    "TRACK_NEGOTIATION_METRICS": True,
    "METRICS_RETENTION_DAYS": 365,
}

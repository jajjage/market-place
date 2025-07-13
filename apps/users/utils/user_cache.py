from django.core.cache import cache


# Alternative approach using cache utility functions
def get_user_profile_cache_key(user_id):
    return f"user_profile_{user_id}"


def get_cached_user_profile(user_id):
    cache_key = get_user_profile_cache_key(user_id)
    return cache.get(cache_key)


def set_user_profile_cache(user_id, data, timeout=900):
    cache_key = get_user_profile_cache_key(user_id)
    cache.set(cache_key, data, timeout)


def invalidate_user_profile_cache(user_id):
    cache_key = get_user_profile_cache_key(user_id)
    cache.delete(cache_key)


def invalidate_analytics_cache(user_id, analytics_type):
    """Invalidate cache for specific analytics type."""
    cache_key = f"{analytics_type}_analytics_{user_id}"
    cache.delete(cache_key)

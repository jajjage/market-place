# -----------------------------------------------------------------------------
# CENTRALIZED CACHE-KEY TEMPLATES
#
# For each “resource” you want to cache, list every “key name” you might use.
# Use Python‐format placeholders for variable parts.
#
# Usage:
#    CacheKeyManager.make_key("brand", "detail", id=42)
#    → "brand:detail:42"
#
#    CacheKeyManager.make_key("inventory", "stock", id=10, variant=3)
#    → "inventory:stock:10:3"
#
#    CacheKeyManager.make_pattern("brand", "variants", id=42)
#    → "brand:variants:42:*"
#
# The code will always prepend Django’s KEY_PREFIX automatically.
# -----------------------------------------------------------------------------
CACHE_KEY_TEMPLATES = {
    "product_catalog": {
        # Your requested key pattern: product_catalog:all:page:{n}:sort:{criteria}:v{version}
        "all_paginated": "product_catalog:all:page:{page}:sort:{sort_criteria}:v{version}",
        "all_pattern": "product_catalog:all:*",  # For bulk deletion - NO PLACEHOLDERS
        # Other catalog keys
        "category_list": "product_catalog:category:{category_id}:page:{page}:sort:{sort_criteria}:v{version}",
        "brand_list": "product_catalog:brand:{brand_id}:page:{page}:sort:{sort_criteria}:v{version}",
        "search_results": "product_catalog:search:{search_hash}:page:{page}:sort:{sort_criteria}:v{version}",
        # Wildcard patterns for bulk deletion - SOME REQUIRE PARAMS
        "category_pattern": "product_catalog:category:{category_id}:*",  # Requires category_id
        "brand_pattern": "product_catalog:brand:{brand_id}:*",  # Requires brand_id
        "search_pattern": "product_catalog:search:*",  # No params needed
    },
    "product_base": {
        "detail": "product_base:detail:{id}",
        "detail_by_shortcode": "product_base:detail_by_shortcode:{short_code}",
        # FIXED: Separate exact keys from patterns
        "list": "product_base:list:{params}",  # For exact keys
        "list_all_pattern": "product_base:list:*",  # For ALL list deletion - NO PARAMS NEEDED
        "my_products": "product_base:my_products:{user_id}",
        "my_products_pattern": "product_base:my_products:*",  # For ALL user products - NO PARAMS
        "featured": "product_base:featured",
        "stats": "product_base:stats:{user_id}",
        "stats_pattern": "product_base:stats:*",  # For ALL user stats - NO PARAMS
        "watchers": "product_base:watchers:{id}",
        "watchers_pattern": "product_base:watchers:*",  # For ALL watchers - NO PARAMS
        "share_links": "product_base:share_links:{short_code}",
        "share_links_pattern": "product_base:share_links:*",  # For ALL share links - NO PARAMS
        "by_condition": "product_base:by_condition:{condition_id}",
        "by_condition_pattern": "product_base:by_condition:*",  # For ALL conditions - NO PARAMS
        "toggle_active": "product_base:toggle_active:{id}",
        "toggle_featured": "product_base:toggle_featured:{id}",
        # Specific user patterns - REQUIRE user_id parameter
        "user_specific_pattern": "product_base:my_products:{user_id}",  # Specific user only
        "user_stats_pattern": "product_base:stats:{user_id}",  # Specific user stats
    },
    "brand": {
        # Exact keys (no wildcard) → use make_key("brand", key_name, **kwargs)
        "detail": "brand:detail:{id}",
        "stats": "brand:stats:{id}",
        "analytics": "brand:analytics:{brand_id}:{days}",  # Added missing analytics key
        # Wildcard patterns → use make_pattern("brand", key_name, **kwargs)
        "variants": "brand:variants:{id}:{variant_id}",  # for a single variant
        "variants_all": "brand:variants:{id}:*",  # wildcard to delete all variants
        "featured": "brand:featured:*",  # Fixed: changed from "brands:" to "brand:"
        "list": "brand:list:*",  # wildcard for all paginated lists
        # Additional patterns for comprehensive invalidation
        "all_analytics": "brand:analytics:*",  # wildcard for all analytics
        "all_stats": "brand:stats:*",  # wildcard for all stats
        "all_details": "brand:detail:*",  # wildcard for all details
    },
    "brand_variant": {
        "all": "brand:variants:{brand_id}:*",
        "types": "brand",
        # for invalidating all variants of a brand
    },
    "product_condition": {
        "detail": "condition:detail:{id}",
        "list": "condition:list:*",
        "active_conditions": "condition:active_conditions:{include_stats}",
        "popular_conditions": "condition:popular_conditions:{limit}",
        "analytics": "condition:analytics:{condition_id}",
    },
    "product_variant": {
        "types": "variant:types:active_only:{active_only}:with_options:{with_options}",
        "detail": "variant:detail:{params}",
        "options": "variant:options:product_id:{product_id}:option_ids:{option_ids}",
        "popular_conditions": "variant:popular_conditions:{limit}",
        "analytics": "variant:analytics:{variant_id}",
    },
    "product_inventory": {
        "detail": "inventory:detail:{id}",
        "price_stats": "inventory:price_stats:{id}",
        "stock": "inventory:stock:{id}:{variant_id}",
        "stock_all": "inventory:stock:{id}:*",  # wildcard for all stock keys of an item
        "list": "inventory:list:*",
    },
    "product_watchlist": {
        "user_list": "watchlist:user:{id}:items",  # for a single user’s watchlist
        "items_all": "watchlist:items:{id}:*",  # wildcard to delete all items of a user
    },
    # Cache configuration in settings
    "product_image": {
        "list": "image:list:{product_id}",
        "primary": "image:primary:{product_id}",
        "variants": "image:variants:{product_id}",
        "variants_all": "image:variants:{product_id}:*",  # For invalidation
    },
    "product_detail": {
        "list": "detail:list:{product_id}",
        "grouped": "detail:grouped:{product_id}",
        "highlighted": "detail:highlighted:{product_id}",
        "template": "detail:template:{template_id}",
        "category": "detail:category:{category_id}",
        "detail_type": "detail:type:{detail_type}",
    },
    "product_meta": {
        "detail": "meta:detail:{id}",
        "list": "meta:list",
        "featured": "meta:featured",
        "views_buffer": "meta:views_buffer:{id}",
    },
    "category": {
        "detail": "category:detail:{id}",
        "list": "category:list",
        "tree": "category:tree:{max_depth}:{include_inactive}",
        "subcategory_ids": "category:subcategory_ids:{category_id}",
        "popular_categories": "category:popular_categories:{limit}",
        "breadcrumb_path": "category:breadcrumb_path:{category_id}",
    },
    "escrow_transaction": {
        "detail": "escrow:transaction:detail:{id}",
        "list_user": "escrow:transaction:list:{user_id}:{params}",
        "my_purchases": "escrow:transaction:purchases:user:{user_id}",
        "my_sales": "escrow:transaction:sales:{user_id}",
        "tracking": "escrow:transaction:{user_id}:{tracking_id}",
        "status_counts": "escrow:transaction:counts:{user_id}",
    },
    "negotiation": {
        "detail": "negotiation:detail:{id}",
        "user_list": "negotiation:user:{user_id}:status:{status}:role:{role}:product:{product}",
        "stats": "negotiation:stats:product:{product_id}",
        "user_history": "negotiation:history:user:{user_id}:limit:{limit}",
        "active_count": "negotiation:active:user:{user_id}",
        # Wildcard patterns for invalidation
        "user_all": "negotiation:user:{user_id}:*",
        "product_all": "negotiation:*:product:{product_id}:*",
    },
    "product_rating": {
        "detail": "ratings:detail:{id}",
        "list": "ratings:list:{product_id}:params:{params}",
        "user_list": "ratings:user:{user_id}:params:{params}",
        "user_stats": "ratings:user_stats:{user_id}",
        "aggregate": "ratings:aggregate:{product_id}",
        "can_rate": "ratings:can_rate:{product_id}",
        "recent": "ratings:recent:limit:{limit}",
        "flagged": "ratings:flagged",
        # Wildcard patterns for bulk deletion
        "all_ratings": "ratings:*",  # For all ratings
    },
    "watchlist": {
        "stats": "watchlist:stats:user:{user_id}",
        "recently_added": "watchlist:recently_added:user:{user_id}",
        "insights": "watchlist:insights:user:{user_id}",
        "most_watched_categories": "watchlist:most_watched_categories:user:{user_id}",
        "check_product": "watchlist:check_product:user:{user_id}:product:{product_id}",
        "by_product": "watchlist:by_product:product:{product_id}",
        "product_count": "watchlist:product_count:product:{product_id}",
        "toggle_product": "watchlist:toggle_product:user:{user_id}:product:{product_id}",
        # Wildcard patterns for bulk deletion
    },
    "rating": {
        "detail": "ratings:detail:{id}",
        "list": "ratings:list:user_id:{user_id}:page:{page}",
        "eligibility": "ratings:eligibility:buyer_id:{buyer_id}:seller_id:{seller_id}",
        "pending": "ratings:pending:user_id:{user_id}",
        "aggregate": "ratings:aggregate:{product_id}",
        "can_rate": "ratings:can_rate:{product_id}",
        "recent": "ratings:recent:limit:{limit}",
    },
    "dispute": {
        "detail": "dispute:detail:{id}",
        "user_list": "dispute:list:user_id:{user_id}:status:{status}",
        "stats": "dispute:stats:user_id:{user_id}",
        "open_disputes": "dispute:open:user_id:{user_id}",
    },
    # …add new resources here as needed…
}

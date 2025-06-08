import uuid


class BreadcrumbService:
    """Alternative service implementation with more features"""

    HOME_NAME = "TrustLock"
    HOME_URL = "/"

    @staticmethod
    def for_product(product, include_home=True, include_brand=True):
        """Generate breadcrumbs for product with options"""
        breadcrumbs = []
        order = 0

        # Add home
        if include_home:
            breadcrumbs.append(
                BreadcrumbService._create_breadcrumb(
                    id=str(uuid.uuid4()),
                    name=BreadcrumbService.HOME_NAME,
                    href=BreadcrumbService.HOME_URL,
                    order=order,
                )
            )
            order += 1

        # Add category hierarchy
        if hasattr(product, "category") and product.category:
            category_crumbs = BreadcrumbService._get_category_breadcrumbs(
                product.category, start_order=order
            )
            breadcrumbs.extend(category_crumbs)
            order += len(category_crumbs)

        # Add brand
        if include_brand and hasattr(product, "brand") and product.brand:
            breadcrumbs.append(
                BreadcrumbService._create_breadcrumb(
                    id=str(product.brand.id),
                    name=product.brand.name,
                    href=f"/explore?brand={product.brand.slug}",
                    order=order,
                )
            )
            order += 1

        # Add product
        breadcrumbs.append(
            BreadcrumbService._create_breadcrumb(
                id=str(product.id), name=product.title, href=None, order=order
            )
        )

        return breadcrumbs

    @staticmethod
    def for_category(category, include_home=True):
        """Generate breadcrumbs for category"""
        breadcrumbs = []
        order = 0

        # Add home
        if include_home:
            breadcrumbs.append(
                BreadcrumbService._create_breadcrumb(
                    id=str(uuid.uuid4()),
                    name=BreadcrumbService.HOME_NAME,
                    href=BreadcrumbService.HOME_URL,
                    order=order,
                )
            )
            order += 1

        # Add category hierarchy
        category_crumbs = BreadcrumbService._get_category_breadcrumbs(
            category, start_order=order
        )
        breadcrumbs.extend(category_crumbs)

        return breadcrumbs

    @staticmethod
    def _get_category_breadcrumbs(category, start_order=0):
        """Get breadcrumbs for category hierarchy"""
        path = BreadcrumbService._get_category_path(category)
        breadcrumbs = []

        for i, cat in enumerate(path):
            breadcrumbs.append(
                BreadcrumbService._create_breadcrumb(
                    id=str(cat.id),
                    name=cat.name,
                    href=f"/explore?category={cat.slug}",
                    order=start_order + i,
                )
            )

        return breadcrumbs

    @staticmethod
    def _get_category_path(category):
        """Get full category path including ancestors"""
        ancestors = []
        current = getattr(category, "parent", None)
        while current:
            ancestors.insert(0, current)
            current = getattr(current, "parent", None)

        path = ancestors[:]
        path.append(category)
        return path

    @staticmethod
    def _create_breadcrumb(id, name, href, order):
        """Create a breadcrumb dictionary"""
        return {"id": id, "name": name, "href": href, "order": order}

    @staticmethod
    def generate_transaction_breadcrumbs(transaction, include_home=True):
        """Generate breadcrumbs for transaction"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add user profile (buyer/seller context)
        if hasattr(transaction, "buyer") and transaction.buyer:
            breadcrumbs.append(
                {
                    "id": str(transaction.buyer.id),
                    "name": "My Account",
                    "href": "/profile",
                    "order": order,
                }
            )
            order += 1

        # Add transactions section
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Transactions",
                "href": "/transactions",
                "order": order,
            }
        )
        order += 1

        # Add current transaction
        breadcrumbs.append(
            {
                "id": str(transaction.id),
                "name": f"Transaction #{transaction.id}",
                "href": None,
                "order": order,
            }
        )

        return breadcrumbs

    @staticmethod
    def generate_dispute_breadcrumbs(dispute, include_home=True):
        """Generate breadcrumbs for dispute"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add user context
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "My Account",
                "href": "/profile",
                "order": order,
            }
        )
        order += 1

        # Add related transaction if exists
        if hasattr(dispute, "transaction") and dispute.transaction:
            breadcrumbs.append(
                {
                    "id": str(dispute.transaction.id),
                    "name": f"Transaction #{dispute.transaction.id}",
                    "href": f"/transactions/{dispute.transaction.id}",
                    "order": order,
                }
            )
            order += 1

        # Add disputes section
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Disputes",
                "href": "/disputes",
                "order": order,
            }
        )
        order += 1

        # Add current dispute
        breadcrumbs.append(
            {
                "id": str(dispute.id),
                "name": f"Dispute #{dispute.id}",
                "href": None,
                "order": order,
            }
        )

        return breadcrumbs

    @staticmethod
    def generate_store_breadcrumbs(store, include_home=True):
        """Generate breadcrumbs for store"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add stores section
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Stores",
                "href": "/stores",
                "order": order,
            }
        )
        order += 1

        # Add current store
        breadcrumbs.append(
            {"id": str(store.id), "name": store.name, "href": None, "order": order}
        )

        return breadcrumbs

    @staticmethod
    def generate_userprofile_breadcrumbs(user_profile, include_home=True):
        """Generate breadcrumbs for user profile"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add current user profile
        breadcrumbs.append(
            {
                "id": str(user_profile.id),
                "name": "My Profile",
                "href": None,
                "order": order,
            }
        )

        return breadcrumbs

    @staticmethod
    def generate_watchlist_breadcrumbs(watchlist_item, include_home=True):
        """Generate breadcrumbs for watchlist - extends product breadcrumbs"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add user context
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "My Account",
                "href": "/profile",
                "order": order,
            }
        )
        order += 1

        # Add watchlist section
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Watchlist",
                "href": "/watchlist",
                "order": order,
            }
        )
        order += 1

        # Add product if available
        if hasattr(watchlist_item, "product") and watchlist_item.product:
            breadcrumbs.append(
                {
                    "id": str(watchlist_item.product.id),
                    "name": watchlist_item.product.title,
                    "href": f"/products/{watchlist_item.product.id}",
                    "order": order,
                }
            )

        return breadcrumbs

    # ========================================
    # PRODUCT-RELATED BREADCRUMBS (Extend product breadcrumbs)
    # ========================================

    @staticmethod
    def generate_product_rating_breadcrumbs(rating, include_home=True):
        """Generate breadcrumbs for product rating - extends product"""
        if not hasattr(rating, "product") or not rating.product:
            return []

        # Get product breadcrumbs first
        product_breadcrumbs = BreadcrumbService.generate_product_breadcrumbs(
            rating.product, include_home
        )

        # Remove the product from end (since we'll add rating section)
        if product_breadcrumbs:
            product_breadcrumbs.pop()  # Remove product

        # Add reviews section
        product_breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Reviews",
                "href": f"/products/{rating.product.id}/reviews",
                "order": len(product_breadcrumbs),
            }
        )

        # Add current rating
        product_breadcrumbs.append(
            {
                "id": str(rating.id),
                "name": f"Review by {rating.user.username if hasattr(rating, 'user') else 'User'}",
                "href": None,
                "order": len(product_breadcrumbs),
            }
        )

        return product_breadcrumbs

    @staticmethod
    def generate_product_negotiation_breadcrumbs(negotiation, include_home=True):
        """Generate breadcrumbs for negotiation - extends product"""
        if not hasattr(negotiation, "product") or not negotiation.product:
            return []

        # Get product breadcrumbs first
        product_breadcrumbs = BreadcrumbService.generate_product_breadcrumbs(
            negotiation.product, include_home
        )

        # Remove the product from end
        if product_breadcrumbs:
            product_breadcrumbs.pop()

        # Add negotiations section
        product_breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Negotiations",
                "href": f"/products/{negotiation.product.id}/negotiations",
                "order": len(product_breadcrumbs),
            }
        )

        # Add current negotiation
        product_breadcrumbs.append(
            {
                "id": str(negotiation.id),
                "name": f"Negotiation #{negotiation.id}",
                "href": None,
                "order": len(product_breadcrumbs),
            }
        )

        return product_breadcrumbs

    # ========================================
    # APPS THAT DON'T NEED BREADCRUMBS
    # ========================================

    # These apps typically don't need breadcrumbs as they're:
    # - image: Usually displayed within product context
    # - variant: Part of product detail, not standalone pages
    # - condition: Usually a filter/attribute, not a page
    # - metadata: Backend data, not user-facing pages

    # ========================================
    # UTILITY METHOD FOR GENERIC BREADCRUMBS
    # ========================================

    @staticmethod
    def generate_generic_breadcrumbs(
        entity, entity_name, list_url=None, include_home=True
    ):
        """Generic breadcrumb generator for simple entities"""
        breadcrumbs = []
        order = 0

        if include_home:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrustLock",
                    "href": "/",
                    "order": order,
                }
            )
            order += 1

        # Add list page if provided
        if list_url:
            breadcrumbs.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": entity_name.title(),
                    "href": list_url,
                    "order": order,
                }
            )
            order += 1

        # Add current entity
        entity_display_name = getattr(entity, "name", None) or getattr(
            entity, "title", f"{entity_name} #{entity.id}"
        )
        breadcrumbs.append(
            {
                "id": str(entity.id),
                "name": entity_display_name,
                "href": None,
                "order": order,
            }
        )

        return breadcrumbs

import uuid


class BreadcrumbServiceV2:
    """Alternative service implementation with more features"""

    def __init__(self, home_name="TrustLock", home_url="/"):
        self.home_name = home_name
        self.home_url = home_url

    def for_product(self, product, include_home=True, include_brand=True):
        """Generate breadcrumbs for product with options"""
        breadcrumbs = []
        order = 0

        # Add home
        if include_home:
            breadcrumbs.append(
                self._create_breadcrumb(
                    id=str(uuid.uuid4()),
                    name=self.home_name,
                    href=self.home_url,
                    order=order,
                )
            )
            order += 1

        # Add category hierarchy
        if hasattr(product, "category") and product.category:
            category_crumbs = self._get_category_breadcrumbs(
                product.category, start_order=order
            )
            breadcrumbs.extend(category_crumbs)
            order += len(category_crumbs)

        # Add brand
        if include_brand and hasattr(product, "brand") and product.brand:
            breadcrumbs.append(
                self._create_breadcrumb(
                    id=str(product.brand.id),
                    name=product.brand.name,
                    href=f"/explore?brand={product.brand.slug}",
                    order=order,
                )
            )
            order += 1

        # Add product
        breadcrumbs.append(
            self._create_breadcrumb(
                id=str(product.id), name=product.title, href=None, order=order
            )
        )

        return breadcrumbs

    def for_category(self, category, include_home=True):
        """Generate breadcrumbs for category"""
        breadcrumbs = []
        order = 0

        # Add home
        if include_home:
            breadcrumbs.append(
                self._create_breadcrumb(
                    id=str(uuid.uuid4()),
                    name=self.home_name,
                    href=self.home_url,
                    order=order,
                )
            )
            order += 1

        # Add category hierarchy
        category_crumbs = self._get_category_breadcrumbs(category, start_order=order)
        breadcrumbs.extend(category_crumbs)

        return breadcrumbs

    def _get_category_breadcrumbs(self, category, start_order=0):
        """Get breadcrumbs for category hierarchy"""
        path = self._get_category_path(category)
        breadcrumbs = []

        for i, cat in enumerate(path):
            breadcrumbs.append(
                self._create_breadcrumb(
                    id=str(cat.id),
                    name=cat.name,
                    href=f"/explore?category={cat.slug}",
                    order=start_order + i,
                )
            )

        return breadcrumbs

    def _get_category_path(self, category):
        """Get full category path including ancestors"""
        ancestors = []
        current = getattr(category, "parent", None)
        while current:
            ancestors.insert(0, current)
            current = getattr(current, "parent", None)

        path = ancestors[:]
        path.append(category)
        return path

    def _create_breadcrumb(self, id, name, href, order):
        """Create a breadcrumb dictionary"""
        return {"id": id, "name": name, "href": href, "order": order}

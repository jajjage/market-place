import uuid


class Category:
    def get_ancestors(self):
        """Get all parent categories up to root in correct order"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)  # Insert at beginning for correct order
            current = current.parent
        return ancestors

    def get_breadcrumb_path(self):
        """Get full breadcrumb path including self"""
        path = self.get_ancestors()
        path.append(self)
        return path

    def get_breadcrumb_data(self):
        """Get breadcrumb data in your format"""
        breadcrumbs = []

        # Add home
        breadcrumbs.append(
            {
                "id": str(uuid.uuid4()),
                "name": "TrustLock",
                "href": "/",
                "order": 0,
            }
        )

        # Add category hierarchy
        for i, category in enumerate(self.get_breadcrumb_path()):
            breadcrumbs.append(
                {
                    "id": str(category.id),
                    "name": category.name,
                    "href": f"/explore?category={category.slug}",
                    "order": i + 1,
                }
            )

        return breadcrumbs

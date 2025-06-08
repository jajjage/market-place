from apps.categories.models import Category
from apps.products.product_base.models import Product


class BreadcrumbService:
    """
    Dynamic breadcrumb service - much simpler than your current one
    """

    @staticmethod
    def get_product_breadcrumbs(product_id):
        """Get breadcrumbs for a specific product"""
        try:
            product = Product.objects.select_related("category", "brand").get(
                id=product_id
            )
            return product.get_breadcrumb_path()
        except Product.DoesNotExist:
            return []

    @staticmethod
    def get_category_breadcrumbs(category_id):
        """Get breadcrumbs for a specific category"""
        try:
            category = Category.objects.get(id=category_id)
            return category.get_breadcrumb_data()
        except Category.DoesNotExist:
            return []

    @staticmethod
    def get_breadcrumbs_by_slug(product_slug):
        """Get breadcrumbs by product slug"""
        try:
            product = Product.objects.select_related("category", "brand").get(
                slug=product_slug
            )
            return product.get_breadcrumb_path()
        except Product.DoesNotExist:
            return []

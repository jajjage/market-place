import uuid
from django.utils.text import slugify
from django.db import models

from apps.core.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

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
                "id": str(
                    uuid.uuid4()
                ),  # Generate UUID for consistency with your format
                "name": "TrustLock",
                "href": "/",
                "order": 0,
            }
        )

        # Add category hierarchy
        for i, category in enumerate(self.get_breadcrumb_path()):
            breadcrumbs.append(
                {
                    "id": str(category.id),  # Use category ID
                    "name": category.name,
                    "href": f"/explore?category={category.slug}",
                    "order": i + 1,
                }
            )

        return breadcrumbs

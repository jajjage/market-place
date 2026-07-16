from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.categories.models import Category
from apps.products.models import Brand, ProductCondition, Product, ProductDetail, ProductMeta

User = get_user_model()

class Command(BaseCommand):
    help = "Seed product database with standard test data for search and indexing"

    def handle(self, *args, **options):
        self.stdout.write("Seeding test data for search...")

        # 1. Get or create seller user
        seller, created = User.objects.get_or_create(
            email="seller@example.com",
            defaults={
                "is_active": True,
                "first_name": "Test",
                "last_name": "Seller",
            }
        )
        if created:
            seller.set_password("password123")
            seller.save()
            self.stdout.write("Created test_seller user")

        # 2. Get or create categories
        categories_data = [
            ("Electronics", "Gadgets and laptops", "electronics"),
            ("Fashion", "Clothing and traditional wear", "fashion"),
            ("Home & Kitchen", "Appliances and cookware", "home-kitchen"),
        ]
        categories = {}
        for name, desc, slug in categories_data:
            cat, created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": desc, "is_active": True}
            )
            categories[slug] = cat
            if created:
                self.stdout.write(f"Created category: {name}")

        # 3. Get or create brands
        brands_data = [
            ("HP", "Hewlett-Packard laptops and computers", "hp", "USA"),
            ("Gucci", "Italian luxury fashion brand", "gucci", "Italy"),
            ("Samsung", "Electronics, mobile phones and displays", "samsung", "South Korea"),
        ]
        brands = {}
        for name, desc, slug, country in brands_data:
            brand, created = Brand.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "country_of_origin": country,
                    "is_active": True,
                }
            )
            brands[slug] = brand
            if created:
                self.stdout.write(f"Created brand: {name}")

        # 4. Get or create product conditions
        conditions_data = [
            ("Brand New", "In original packaging, never used", "new", 10, 1.000, 1, "#28a745", "star"),
            ("Like New / Excellent", "Very light signs of use", "good", 8, 0.850, 2, "#17a2b8", "check-circle"),
            ("Fair / Heavily Used", "Visible signs of wear and tear", "fair", 5, 0.600, 3, "#ffc107", "exclamation-circle"),
        ]
        conditions = {}
        for name, desc, slug, quality, factor, order, color, icon in conditions_data:
            cond, created = ProductCondition.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "quality_score": quality,
                    "price_factor": factor,
                    "display_order": order,
                    "color_code": color,
                    "icon_name": icon,
                    "is_active": True,
                }
            )
            conditions[slug] = cond
            if created:
                self.stdout.write(f"Created condition: {name}")

        # 5. Get or create products
        products_data = [
            {
                "title": "HP Pavilion Plus 14 Laptop",
                "description": "High performance Intel Core i7 laptop with 16GB RAM and 512GB SSD. Beautiful OLED screen.",
                "price": 650.00,
                "original_price": 850.00,
                "category": categories["electronics"],
                "brand": brands["hp"],
                "condition": conditions["good"],
                "location": "Lagos",
                "is_featured": True,
                "is_negotiable": True,
                "requires_shipping": True,
                "authenticity_guaranteed": True,
                "seo_keywords": ["laptop", "hp", "pavilion", "oled", "computer", "windows"],
                "details": [
                    ("RAM", "16", "GB"),
                    ("Storage", "512", "GB"),
                    ("OS", "Windows 11 Home", ""),
                ]
            },
            {
                "title": "Samsung Galaxy S23 Ultra",
                "description": "Flagship android phone. 256GB storage, 12GB RAM, 200MP camera. Midnight Black colour.",
                "price": 950.00,
                "original_price": 1150.00,
                "category": categories["electronics"],
                "brand": brands["samsung"],
                "condition": conditions["new"],
                "location": "Lagos",
                "is_featured": True,
                "is_negotiable": False,
                "requires_shipping": True,
                "authenticity_guaranteed": True,
                "seo_keywords": ["samsung", "galaxy", "ultra", "smartphone", "android", "camera"],
                "details": [
                    ("RAM", "12", "GB"),
                    ("Storage", "256", "GB"),
                    ("Screen Size", "6.8", "inches"),
                ]
            },
            {
                "title": "Gucci Leather Marmont Bag",
                "description": "Authentic Gucci double G logo quilted leather bag. Very light signs of wear on the strap.",
                "price": 1200.00,
                "original_price": 1500.00,
                "category": categories["fashion"],
                "brand": brands["gucci"],
                "condition": conditions["good"],
                "location": "Abuja",
                "is_featured": False,
                "is_negotiable": True,
                "requires_shipping": True,
                "authenticity_guaranteed": True,
                "seo_keywords": ["bag", "gucci", "leather", "shoulder", "purse", "luxury"],
                "details": [
                    ("Material", "Quilted Leather", ""),
                    ("Color", "Black", ""),
                ]
            },
            {
                "title": "Babbar Riga Traditional Attire",
                "description": "Beautiful traditional hand-embroidered Hausa attire for special occasions. Excellent condition.",
                "price": 180.00,
                "original_price": 250.00,
                "category": categories["fashion"],
                "brand": None,
                "condition": conditions["good"],
                "location": "Kano",
                "is_featured": False,
                "is_negotiable": True,
                "requires_shipping": True,
                "authenticity_guaranteed": False,
                "seo_keywords": ["riga", "traditional", "northern", "embroidery", "native"],
                "details": [
                    ("Fabric", "Premium Brocade", ""),
                    ("Embroidery", "Handmade", ""),
                ]
            },
            {
                "title": "Vintage HP Printer",
                "description": "Heavy old printer. Dusty and untested. Selling as-is.",
                "price": 40.00,
                "original_price": 100.00,
                "category": categories["electronics"],
                "brand": brands["hp"],
                "condition": conditions["fair"],
                "location": "Ibadan",
                "is_featured": False,
                "is_negotiable": True,
                "requires_shipping": False,
                "authenticity_guaranteed": False,
                "seo_keywords": ["printer", "hp", "vintage", "office"],
                "details": [
                    ("Status", "Untested", ""),
                ]
            }
        ]

        for p_data in products_data:
            details_list = p_data.pop("details")
            seo_kw = p_data.pop("seo_keywords")
            
            p, created = Product.objects.get_or_create(
                title=p_data["title"],
                seller=seller,
                defaults={
                    "description": p_data["description"],
                    "price": p_data["price"],
                    "original_price": p_data["original_price"],
                    "category": p_data["category"],
                    "brand": p_data["brand"],
                    "condition": p_data["condition"],
                    "location": p_data["location"],
                    "is_featured": p_data["is_featured"],
                    "is_negotiable": p_data["is_negotiable"],
                    "requires_shipping": p_data["requires_shipping"],
                    "authenticity_guaranteed": p_data["authenticity_guaranteed"],
                    "status": "active",
                    "is_active": True,
                }
            )

            # Create or update related metadata (where seo_keywords lives)
            meta, _ = ProductMeta.objects.get_or_create(product=p)
            meta.seo_keywords = seo_kw
            meta.seo_generation_queued = False
            meta.save()

            if created:
                self.stdout.write(f"Created product: {p.title}")
                # Create related details
                for label, value, unit in details_list:
                    ProductDetail.objects.create(
                        product=p,
                        label=label,
                        value=value,
                        unit=unit,
                        detail_type="specification",
                        is_active=True,
                    )
            else:
                self.stdout.write(f"Product already exists: {p.title}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded test data!"))

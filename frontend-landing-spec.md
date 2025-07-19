# Frontend Landing Page Specification - Escrow Marketplace Platform

## Brand Identity & Design System

## Page Structure

### 1. Navigation Bar
- Clean, minimal design with transparent background
- Logo on the left
- Main menu items: Home, How It Works, Features, Pricing
- Right-aligned CTAs: Login, Sign Up
- Mobile-responsive hamburger menu

### 2. Hero Section
- Full-width gradient background (using existing gradient from error pages)
- Main heading: "Secure Escrow Services for Your Online Transactions"
- Subheading: "Trust, Security, and Peace of Mind for Buyers and Sellers"
- Primary CTA: "Get Started" (blue gradient button)
- Secondary CTA: "Learn More" (white outline button)
- Floating statistics cards showing:
  - Total Transaction Volume
  - Active Users
  - Successful Transactions
  - Buyer Protection Guarantee

### 3. How It Works Section
Three-column layout showcasing the escrow process:
1. "Secure Payment" card
2. "Protected Holding" card
3. "Safe Release" card
Each with corresponding icons and brief explanations

### 4. Key Features Grid
Six-feature grid highlighting:
- Buyer Protection
- Seller Security
- Dispute Resolution
- Real-time Chat
- Payment Security
- Transaction Tracking

### 5. Trust & Security Section
- Security badges and certifications
- User verification system highlights
- Protection guarantees
- Integration with known payment providers
- Anti-fraud measures

### 6. User Benefits Section
Split into two columns:
- **For Buyers**:
  - Purchase Protection
  - Secure Payments
  - Quality Guarantee
- **For Sellers**:
  - Payment Security
  - Verified Buyers
  - Easy Withdrawals

### 7. Call-to-Action Section
- Background: Blue gradient (matching error pages)
- Heading: "Start Secure Trading Today"
- Subheading: "Join thousands of satisfied users"
- Sign-up form or button
- "No credit card required" trust badge

### 8. Footer
- Company information
- Quick links
- Legal documents
- Social media links
- Newsletter signup

## Interactive Elements

### Micro-interactions
- Hover effects on buttons (subtle scale and color change)
- Smooth scroll navigation
- Progressive loading of statistics
- Animated icons in How It Works section

### Trust Indicators
- Live transaction counter
- User testimonials carousel
- Security badges
- Verification checkmarks

## Mobile Responsiveness
- Fully responsive design for all screen sizes
- Simplified navigation on mobile
- Stacked layouts for smaller screens
- Touch-friendly buttons and interactions

## Technical Considerations
- Preload critical fonts and images
- Optimize for Core Web Vitals
- Progressive image loading
- Accessibility compliance (WCAG 2.1)
- SEO optimization for escrow service keywords

## Integration Points
- Authentication system connection
- Real-time transaction updates
- User notification system
- Chat system integration
- Payment gateway connections









this is the method that get list of product get_cached_product_list and inside it i do thiss if viewset.action != "list":             return ProductListService.get_product_queryset(queryset) which i contruct queryset here   @staticmethod     def get_product_queryset(queryset):         """         Get optimized product queryset with related fields and annotations.         This method is used to ensure efficient data retrieval for product details.          Args:             base_queryset: Base Product queryset          Returns:             Optimized queryset with select_related and prefetch_related         """         # Only select the fields we need from related models         base_queryset = queryset.select_related(             "brand",             "category",             "condition",             "seller",             "seller__profile",             "meta",         ).only(             "id",             "title",             "price",             "original_price",             "currency",             "slug",             "short_code",             "is_active",             "is_featured",             "status",             "description",             "location",             "escrow_fee",             "requires_inspection",             "brand__id",             "brand__name",             "category__id",             "category__name",             "condition__id",             "condition__name",             "seller__id",             "seller__first_name",             "seller__last_name",             "seller__email",             "seller__profile__id",             "seller__profile__avatar_url",             "meta__id",             "meta__views_count",         )          # Optimize rating queries by prefetching only approved ratings with minimal user info         approved_ratings_prefetch = Prefetch(             "ratings",             queryset=ProductRating.objects.filter(is_approved=True)             .select_related("user")             .only("id", "rating", "user_id", "is_verified_purchase", "is_approved"),             to_attr="approved_ratings",         )          # Optimize image queries by prefetching only necessary fields         primary_images_prefetch = Prefetch(             "images",             queryset=ProductImage.objects.filter(is_active=True, is_primary=True).only(                 "id", "product_id", "is_primary", "display_order"             ),             to_attr="primary_images",         )          all_images_prefetch = Prefetch(             "images",             queryset=ProductImage.objects.filter(is_active=True)             .only("id", "product_id", "is_primary", "display_order")             .order_by("display_order"),             to_attr="all_active_images",         )          # Optimize variants query with minimal fields         variants_prefetch = Prefetch("variants", to_attr="product_variants")          # Use conditional annotations to reduce unnecessary joins         optimized_qs = base_queryset.prefetch_related(             primary_images_prefetch,             all_images_prefetch,             variants_prefetch,             approved_ratings_prefetch,         ).annotate(             avg_rating_db=Avg("ratings__rating", filter=Q(ratings__is_approved=True)),             ratings_count_db=Count("ratings", filter=Q(ratings__is_approved=True)),             verified_ratings_count=Count(                 "ratings",                 filter=Q(ratings__is_approved=True, ratings__is_verified_purchase=True),             ),             watchers_count=Count("watchers", distinct=True),             total_views=F("meta__views_count"),  # if meta is 1:1         )          return optimized_qs and im having trouble with to much database hit n+1  efault 27.31 ms (38 queries including 31 similar and 10 duplicates ) and after i get the data hunder i use ths fr cache # Generate cache key based on request parameters         cache_key = ProductListService._generate_list_cache_key(viewset.request) here is the code under it @staticmethod     def _generate_list_cache_key(request, version="v1"):         """         Generate cache key based on request parameters.         Enhanced to support versioning and better structure.         """         # Get all query parameters that affect the list         params = {             "page": request.GET.get("page", "1"),             "page_size": request.GET.get("page_size", ""),             "search": request.GET.get("search", ""),             "ordering": request.GET.get("ordering", ""),         }          filter_params = [             "category",             "brand",             "condition",             "seller",             "price_min",             "price_max",             "is_active",             "created_at_after",             "created_at_before",             "inventory_min",         ]          for param in filter_params:             if request.GET.get(param):                 params[param] = request.GET.get(param)          params_str = json.dumps(params, sort_keys=True)         params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]          key = CacheKeyManager.make_key("product_base", "list", params=params_hash)         redis_conn = get_redis_connection("default")         redis_conn.sadd(ProductListService.LIST_KEYS_SET, key)         logger.info(f"Generated cache key: {key} with params: {params}")         return key and if you look at it  does it qualify to give use individual caching or there is other thin to do, continue with main method is that after we get the cache if cache.get(cache_key):             logger.info(f"Cache HIT for product list: {cache_key}")             # Return the cached queryset directly             cached_data = cache.get(cache_key)             if cached_data:                 # Return the cached queryset directly to avoid reconstruction                 return cached_data but the isue also lied in if we get the some data are not directly on product field it related and the i see in debug toolbar the proudct image, condition, brand, category, customuser they are all get call everytime on every single product and may its serializer problem i don't know but here is the serializer class ProductListSerializer(TimestampedModelSerializer):     """     Serializer for listing products with essential information.     Optimized for displaying products in listings.     """      # Use source attribute to directly access nested fields     brand_name = serializers.CharField(source="brand.name", read_only=True)     originalPrice = serializers.DecimalField(         source="original_price",         max_digits=10,         decimal_places=2,         max_value=Decimal("9999999.99"),         min_value=Decimal("0.00"),     )     escrowFee = serializers.DecimalField(         source="escrow_fee",         max_digits=10,         decimal_places=2,         max_value=Decimal("9999999.99"),         min_value=Decimal("0.00"),     )      # Use nested serializer for seller with source to access prefetched relationship     seller = UserShortSerializer(read_only=True)      # Use direct fields from annotations     ratings = serializers.SerializerMethodField()     category_name = serializers.CharField(source="category.name", read_only=True)     condition_name = serializers.CharField(source="condition.name", read_only=True)      # Use custom serializer field for image_url to handle prefetched data     # image_url = serializers.SerializerMethodField()      # Calculate discount percent in the to_representation method     discount_percent = serializers.FloatField(read_only=True)      class Meta:         model = Product         fields = [             "id",             "title",             "price",             "originalPrice",             "currency",             "category_name",             "condition_name",             "requires_inspection",             "is_active",             "is_featured",             "status",             "slug",             "ratings",             "short_code",             "seller",             "escrowFee",             "location",             "description",             "discount_percent",             "brand_name",         ]      def to_representation(self, instance):         """         Override to_representation to handle computed fields and use prefetched data efficiently         """         data = super().to_representation(instance)          # Handle image_url using prefetched data         if hasattr(instance, "primary_images") and instance.primary_images:             data["image_url"] = instance.primary_images[0].image.url         elif hasattr(instance, "all_active_images") and instance.all_active_images:             data["image_url"] = instance.all_active_images[0].image.url         else:             # Fallback to service layer with optimized query             image = ProductImageService.get_primary_image(instance.id, instance)             data["image_url"] = image.image.url if image and image.image else None          # Calculate discount percent         if instance.original_price and instance.price < instance.original_price:             data["discount_percent"] = round(                 ((instance.original_price - instance.price) / instance.original_price)                 * 100,                 1,             )         else:             data["discount_percent"] = 0          return data.   we move if we miss the cache we do    logger.info(f"Cache MISS for product list: {cache_key}")          # Get optimized queryset         optimized_queryset = ProductListService.get_product_queryset(queryset)          # Apply viewset's filtering, searching, and ordering         filtered_queryset = ProductListService._apply_viewset_filters(             viewset, optimized_queryset         )          # Cache the product IDs (not the full objects to save memory)         try:             # Cache the full queryset evaluation, limited to 1000 items             cached_queryset = list(filtered_queryset[:1000])             cache.set(cache_key, cached_queryset, ProductListService.CACHE_TTL)             logger.info(                 f"Cached product list with {len(cached_queryset)} items: {cache_key}"             )         except Exception as e:             logger.warning(f"Failed to cache product list: {str(e)}")          return filtered_queryset  does it going to cahe all the data or what 
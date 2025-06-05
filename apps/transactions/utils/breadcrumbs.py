from django.urls import reverse
from apps.products.product_breadcrumb.services import BreadcrumbService
from apps.transactions.models import EscrowTransaction


def breadcrumbs(context, obj: EscrowTransaction) -> list:
    """
    Custom method to generate and return breadcrumbs for the transaction.
    'obj' here refers to the Transaction instance being serialized.
    """
    request = context.get("request")
    if not request:
        # If request context is not available (e.g., in unit tests without a request factory)
        # return basic breadcrumbs or raise an error depending on strictness.
        return []

    # 1. Get base breadcrumbs from the database (e.g., Home > My Transactions > Transaction #123)
    # Assuming generate_breadcrumbs_for_transaction has been called and populated the DB
    base_breadcrumbs = BreadcrumbService.get_breadcrumbs_for_object(obj)

    # Make a copy to avoid modifying the cached list directly
    dynamic_breadcrumbs = list(base_breadcrumbs)

    # 2. Dynamically add the current page's specific step
    # This part depends on the exact URL and what step it represents.
    # You'll need logic here to determine the current step's name and href based on the request URL.

    current_path = request.path

    # --- Example Logic for Dynamic Steps ---
    # This part requires you to parse the URL and map it to a step name and URL.
    # This is a conceptual example; your actual routing and step naming might differ.
    if f"/api/transactions/{obj.pk}/define-terms/" in current_path:
        dynamic_breadcrumbs.append(
            {
                "name": "Define Terms",
                "href": reverse(
                    "transaction-define-terms", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
    elif f"/api/transactions/{obj.pk}/fund-escrow/" in current_path:
        # For multi-step sequences, include previous dynamic steps if needed
        dynamic_breadcrumbs.append(
            {
                "name": "Define Terms",
                "href": reverse(
                    "transaction-define-terms", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
        dynamic_breadcrumbs.append(
            {
                "name": "Fund Escrow",
                "href": reverse(
                    "transaction-fund-escrow", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
    elif f"/api/transactions/{obj.pk}/release-funds/" in current_path:
        dynamic_breadcrumbs.append(
            {
                "name": "Define Terms",
                "href": reverse(
                    "transaction-define-terms", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
        dynamic_breadcrumbs.append(
            {
                "name": "Fund Escrow",
                "href": reverse(
                    "transaction-fund-escrow", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
        dynamic_breadcrumbs.append(
            {
                "name": "Release Funds",
                "href": reverse(
                    "transaction-release-funds", kwargs={"pk": obj.pk}, request=request
                ),
            }
        )
    # ... Add more elif conditions for other transaction steps ...
    else:
        # If it's just the base transaction detail page, ensure the transaction itself is the last segment
        # This handles cases where generate_breadcrumbs_for_transaction might not add the object title itself
        # or if you want to ensure the last item is always the current page.
        if (
            not dynamic_breadcrumbs
            or dynamic_breadcrumbs[-1]["href"] != request.build_absolute_uri()
        ):
            dynamic_breadcrumbs.append(
                {
                    "name": str(obj.id),  # Or obj.title if it has one
                    "href": request.build_absolute_uri(),
                }
            )

    # Return the list of breadcrumb dictionaries.
    # The BreadcrumbSerializer is used to validate the *structure* of these dictionaries.
    # We don't need to re-serialize them with BreadcrumbSerializer here,
    # as DRF will handle that because 'breadcrumbs' is a SerializerMethodField
    # and we defined it as BreadcrumbSerializer(many=True).
    return dynamic_breadcrumbs

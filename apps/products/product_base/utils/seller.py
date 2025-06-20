def is_product_owner(view, request, *args, **kwargs):
    print("Checking if user is product owner")
    product = view.get_object()
    seller = request.user
    if not product.seller == seller:
        print("User is not the product owner")
        return False
    return True

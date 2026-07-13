def is_product_owner(view, request, product):
    return product.seller == request.user

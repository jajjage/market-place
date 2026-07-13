from rest_framework.pagination import LimitOffsetPagination


class RatingPagination(LimitOffsetPagination):
    default_limit = 5
    max_limit = 20

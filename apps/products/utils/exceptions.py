class WatchlistError(Exception):
    """Base exception for watchlist-related errors."""

    pass


class WatchlistValidationError(WatchlistError):
    """Exception for validation errors in watchlist operations."""

    pass

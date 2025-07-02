def extract_validation_error_message(error):
    """
    Extract a clean error message from Django or DRF ValidationError
    """
    if hasattr(error, "message_dict") and error.message_dict:
        # Django ValidationError with field errors
        first_field = next(iter(error.message_dict))
        first_error = error.message_dict[first_field][0]
        return str(first_error)
    elif hasattr(error, "detail"):
        # DRF ValidationError
        if isinstance(error.detail, dict):
            first_field = next(iter(error.detail))
            first_error = error.detail[first_field][0]
            return str(first_error)
        elif isinstance(error.detail, list):
            return str(error.detail[0])
    elif hasattr(error, "messages") and error.messages:
        # Django ValidationError with messages
        return str(error.messages[0])

    return str(error)

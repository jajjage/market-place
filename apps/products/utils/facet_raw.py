def _get_buckets(raw):
    """
    Turn either {'buckets': [...]} or [...] into a simple list of bucket dicts.
    """
    if isinstance(raw, dict):
        return raw.get("buckets", [])
    if isinstance(raw, list):
        return raw
    return []


def _get_count(bucket):
    """
    Some aggs come back with 'doc_count', others with 'count'.
    """
    return bucket.get("doc_count", bucket.get("count", 0))

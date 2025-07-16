from django.utils.text import slugify


def generate_unique_slugs(names, model, slug_field="slug"):
    """
    Given a list of `names`, returns a list of unique slugs for `model`.
    Checks against existing slugs in the DB and against slugs already generated
    for this batch.
    """
    # 1) Grab all existing slugs
    existing = set(
        model.objects.values_list(slug_field, flat=True).exclude(
            **{f"{slug_field}__exact": ""}
        )
    )

    new_slugs = []
    for name in names:
        base = slugify(name) or "item"
        slug = base
        counter = 1

        # If slug exists either in DB or in our batch so far, bump a counter
        while slug in existing or slug in new_slugs:
            slug = f"{base}-{counter}"
            counter += 1

        new_slugs.append(slug)
        existing.add(slug)

    return new_slugs

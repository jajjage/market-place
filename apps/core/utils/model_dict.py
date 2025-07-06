from django.forms.models import model_to_dict


def advanced_model_to_dict(instance, fields=None, exclude=None, include_relations=True):
    """
    Converts a Django model instance to a dictionary, with enhanced handling
    for related fields (ForeignKey, ManyToManyField, OneToOneField).

    Args:
        instance: The model instance to convert.
        fields (list, optional): A list of field names to include.
        exclude (list, optional): A list of field names to exclude.
        include_relations (bool): If True, recursively converts related models.
    """
    if instance is None:
        return None

    # Get the initial dictionary of the instance's own fields
    data = model_to_dict(instance, fields=fields, exclude=exclude)

    if not include_relations:
        return data

    # Handle related fields
    for field in instance._meta.get_fields():
        # Check if the field is a relation and should be included
        if (fields and field.name not in fields) or (exclude and field.name in exclude):
            continue

        if field.is_relation:
            related_obj = getattr(instance, field.name, None)
            if related_obj is None:
                data[field.name] = None
                continue

            # Handle Many-to-Many and reverse one-to-many relations
            if field.many_to_many or field.one_to_many:
                # Recursively call for each item in the relation manager
                data[field.name] = [
                    advanced_model_to_dict(obj, include_relations=False)
                    for obj in related_obj.all()
                ]
            # Handle ForeignKey and One-to-One relations
            elif field.many_to_one or field.one_to_one:
                # Recursively call for the single related object
                data[field.name] = advanced_model_to_dict(
                    related_obj, include_relations=False
                )

    return data


def model_to_dict_with_relations(instance, fields=None, exclude=None):
    """
    Converts a Django model instance to a dictionary, including related fields.
    """
    if instance is None:
        return None

    # Get the initial dictionary of the instance's own fields
    data = model_to_dict(instance, fields=fields, exclude=exclude)

    # Handle related fields
    for field in instance._meta.get_fields():
        if (fields and field.name not in fields) or (exclude and field.name in exclude):
            continue

        if field.is_relation:
            related_obj = getattr(instance, field.name, None)
            if related_obj is None:
                data[field.name] = None
                continue

            # Handle Many-to-Many and reverse one-to-many relations
            if field.many_to_many or field.one_to_many:
                data[field.name] = [
                    model_to_dict_with_relations(obj, fields=fields, exclude=exclude)
                    for obj in related_obj.all()
                ]
            # Handle ForeignKey and One-to-One relations
            elif field.many_to_one or field.one_to_one:
                data[field.name] = model_to_dict_with_relations(
                    related_obj, fields=fields, exclude=exclude
                )

    return data


def model_to_dict_with_nested_relations(instance, fields=None, exclude=None):
    """
    Converts a Django model instance to a dictionary, including related fields
    and their nested relationships.
    """
    if instance is None:
        return None

    # Get the initial dictionary of the instance's own fields
    data = model_to_dict(instance, fields=fields, exclude=exclude)

    # Handle related fields
    for field in instance._meta.get_fields():
        if (fields and field.name not in fields) or (exclude and field.name in exclude):
            continue

        if field.is_relation:
            related_obj = getattr(instance, field.name, None)
            if related_obj is None:
                data[field.name] = None
                continue

            # Handle Many-to-Many and reverse one-to-many relations
            if field.many_to_many or field.one_to_many:
                data[field.name] = [
                    model_to_dict_with_nested_relations(
                        obj, fields=fields, exclude=exclude
                    )
                    for obj in related_obj.all()
                ]
            # Handle ForeignKey and One-to-One relations
            elif field.many_to_one or field.one_to_one:
                data[field.name] = model_to_dict_with_nested_relations(
                    related_obj, fields=fields, exclude=exclude
                )

    return data


def model_to_dict_with_custom_fields(instance, custom_fields=None):
    """
    Converts a Django model instance to a dictionary, including custom fields.
    """
    if instance is None:
        return None

    # Get the initial dictionary of the instance's own fields
    data = model_to_dict(instance)

    # Include custom fields if provided
    if custom_fields:
        for field_name, field_value in custom_fields.items():
            data[field_name] = field_value

    return data

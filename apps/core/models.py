from django.db import models
from django.db.models.signals import post_delete, pre_delete
from django.utils import timezone

from .managers import SoftDeleteModelManager


class BaseModel(models.Model):
    """
    An abstract base class that provides created_at and updated_at fields
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AllObjectsManager(models.Manager):
    """Manager that includes all records, including soft-deleted ones."""

    def get_queryset(self):
        return super().get_queryset()


class SoftDeleteBaseModel(BaseModel):
    """
    An abstract base model that provides soft delete functionality.
    """

    deleted_at = models.DateTimeField(null=True, blank=True)

    # Override the default manager with a custom one that filters
    # out soft deleted records. If the manager is overridden, the
    # objects property must be redefined.
    objects = SoftDeleteModelManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, hard_delete=False, *args, **kwarg):
        """
        Mark this object as deleted by setting the deleted_at field.

        Args:
            hard_delete (bool): If True, permanently delete the record
        """
        if hard_delete:
            return super().delete(*args, **kwarg)

        pre_delete.send(sender=self.__class__, instance=self)
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
        post_delete.send(sender=self.__class__, instance=self)

    def restore(self):
        """
        Restore a soft-deleted object
        """
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

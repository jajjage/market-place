# utils/import_resolver.py
"""
Django Import Resolver - Utility to avoid circular imports
Usage: Place this in your utils directory and import it where needed
"""

import importlib
from functools import lru_cache
from typing import Any, Dict, Optional, Type
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured


class ImportResolver:
    """
    A utility class to resolve imports dynamically and avoid circular import issues.
    Supports models, serializers, views, and any other Django components.
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def get_class_safe(self, module_path: str, class_name: str) -> Optional[Type]:
        """
        Safely get a class, returning None if it cannot be imported due to circular imports.
        Use this when you want to handle the circular import gracefully.

        Args:
            module_path: The full module path
            class_name: The class name

        Returns:
            The class object or None if import fails
        """
        try:
            return self.get_class(module_path, class_name)
        except ImproperlyConfigured:
            return None

    def get_class_lazy(self, module_path: str, class_name: str) -> callable:
        """
        Return a callable that will import the class when called.
        Useful for breaking circular imports by deferring the import until actually needed.

        Args:
            module_path: The full module path
            class_name: The class name

        Returns:
            A callable that returns the class when invoked

        Example:
            MySerializerLazy = resolver.get_class_lazy('myapp.serializers', 'MySerializer')
            # Later, when you actually need it:
            MySerializer = MySerializerLazy()
        """

        def lazy_getter():
            return self.get_class(module_path, class_name)

        return lazy_getter

    def get_model(self, app_label: str, model_name: str) -> Type:
        """
        Get a model class by app label and model name.

        Args:
            app_label: The Django app label (e.g., 'auth', 'myapp')
            model_name: The model class name (e.g., 'User', 'MyModel')

        Returns:
            The model class

        Example:
            User = resolver.get_model('auth', 'User')
        """
        try:
            return apps.get_model(app_label, model_name)
        except LookupError as e:
            raise ImproperlyConfigured(
                f"Could not find model '{model_name}' in app '{app_label}': {e}"
            )

    @lru_cache(maxsize=128)
    def get_class(self, module_path: str, class_name: str) -> Type:
        """
        Get a class by module path and class name.

        Args:
            module_path: The full module path (e.g., 'myapp.serializers')
            class_name: The class name (e.g., 'MySerializer')

        Returns:
            The class object

        Example:
            MySerializer = resolver.get_class('myapp.serializers', 'MySerializer')
        """
        cache_key = f"{module_path}.{class_name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # First try: normal import
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            self._cache[cache_key] = cls
            return cls
        except AttributeError as e:
            # Second try: reload the module if it's partially initialized
            if "partially initialized module" in str(e) or "has no attribute" in str(e):
                try:
                    # Force reload the module
                    if module_path in importlib.sys.modules:
                        module = importlib.reload(importlib.sys.modules[module_path])
                    else:
                        module = importlib.import_module(module_path)

                    cls = getattr(module, class_name)
                    self._cache[cache_key] = cls
                    return cls
                except (ImportError, AttributeError):
                    # Third try: use delayed import with retry mechanism
                    return self._delayed_import(module_path, class_name, cache_key)
            else:
                raise ImproperlyConfigured(
                    f"Could not import '{class_name}' from '{module_path}': {e}"
                )
        except ImportError as e:
            raise ImproperlyConfigured(
                f"Could not import '{class_name}' from '{module_path}': {e}"
            )

    def _delayed_import(
        self, module_path: str, class_name: str, cache_key: str, max_retries: int = 3
    ) -> Type:
        """
        Delayed import with retry mechanism for circular import situations.
        """
        import time

        for attempt in range(max_retries):
            try:
                # Small delay to allow other imports to complete
                if attempt > 0:
                    time.sleep(0.01 * attempt)  # 10ms, 20ms, 30ms delays

                # Try to get from sys.modules first (might be loaded now)
                if module_path in importlib.sys.modules:
                    module = importlib.sys.modules[module_path]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        self._cache[cache_key] = cls
                        return cls

                # Try fresh import
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                self._cache[cache_key] = cls
                return cls

            except (ImportError, AttributeError):
                if attempt == max_retries - 1:  # Last attempt
                    raise ImproperlyConfigured(
                        f"Could not import '{class_name}' from '{module_path}' after {max_retries} attempts. "
                        f"This likely indicates a circular import that cannot be resolved automatically."
                    )
                continue

    @lru_cache(maxsize=128)
    def get_serializer(
        self,
        app_name: str,
        serializer_name: str,
        fallback_modules: Optional[list] = None,
    ) -> Type:
        """
        Get a serializer class from an app's serializers module.

        Args:
            app_name: The app name (e.g., 'myapp')
            serializer_name: The serializer class name
            fallback_modules: List of alternative module paths to try

        Returns:
            The serializer class

        Example:
            UserSerializer = resolver.get_serializer('accounts', 'UserSerializer')
            # With fallback:
            UserSerializer = resolver.get_serializer(
                'accounts',
                'UserSerializer',
                fallback_modules=['accounts.api.serializers', 'accounts.v1.serializers']
            )
        """
        # Primary module path
        primary_module = f"{app_name}.serializers"

        # Try primary module first
        serializer_class = self.get_class_safe(primary_module, serializer_name)
        if serializer_class:
            return serializer_class

        # Try fallback modules if provided
        if fallback_modules:
            for module_path in fallback_modules:
                serializer_class = self.get_class_safe(module_path, serializer_name)
                if serializer_class:
                    return serializer_class

        # If all else fails, try the standard approach (which may raise an exception)
        return self.get_class(primary_module, serializer_name)

    @lru_cache(maxsize=128)
    def get_view(self, app_name: str, view_name: str) -> Type:
        """
        Get a view class from an app's views module.

        Args:
            app_name: The app name
            view_name: The view class name

        Returns:
            The view class
        """
        return self.get_class(f"{app_name}.views", view_name)

    @lru_cache(maxsize=128)
    def get_form(self, app_name: str, form_name: str) -> Type:
        """
        Get a form class from an app's forms module.

        Args:
            app_name: The app name
            form_name: The form class name

        Returns:
            The form class
        """
        return self.get_class(f"{app_name}.forms", form_name)

    def get_function(self, module_path: str, function_name: str) -> Any:
        """
        Get a function by module path and function name.

        Args:
            module_path: The full module path
            function_name: The function name

        Returns:
            The function object
        """
        cache_key = f"{module_path}.{function_name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, function_name)
            self._cache[cache_key] = func
            return func
        except (ImportError, AttributeError) as e:
            raise ImproperlyConfigured(
                f"Could not import function '{function_name}' from '{module_path}': {e}"
            )

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()
        # Clear LRU caches
        self.get_model.cache_clear()
        self.get_class.cache_clear()
        self.get_serializer.cache_clear()
        self.get_view.cache_clear()
        self.get_form.cache_clear()


# Additional utility for handling circular imports in Django
class CircularImportHandler:
    """
    A specialized handler for managing circular imports in Django projects.
    Use this when you know you have circular import issues and want to handle them gracefully.
    """

    def __init__(self):
        self.resolver = ImportResolver()
        self._pending_imports = set()

    def safe_import(self, module_path: str, class_name: str, default=None):
        """
        Safely import a class, returning a default value if circular import occurs.

        Args:
            module_path: The module path
            class_name: The class name
            default: Default value to return if import fails

        Returns:
            The imported class or default value
        """
        import_key = f"{module_path}.{class_name}"

        # Prevent infinite recursion
        if import_key in self._pending_imports:
            return default

        self._pending_imports.add(import_key)
        try:
            result = self.resolver.get_class_safe(module_path, class_name)
            return result if result is not None else default
        finally:
            self._pending_imports.discard(import_key)

    def get_serializer_safe(self, app_name: str, serializer_name: str, default=None):
        """Safely get a serializer with fallback."""
        return self.safe_import(f"{app_name}.serializers", serializer_name, default)


# Global instances
resolver = ImportResolver()
circular_handler = CircularImportHandler()


# Convenience functions for common use cases
def get_model(app_label: str, model_name: str) -> Type:
    """Convenience function to get a model."""
    return resolver.get_model(app_label, model_name)


def get_serializer(app_name: str, serializer_name: str) -> Type:
    """Convenience function to get a serializer."""
    return resolver.get_serializer(app_name, serializer_name)


def get_class(module_path: str, class_name: str) -> Type:
    """Convenience function to get any class."""
    return resolver.get_class(module_path, class_name)


# Decorator for lazy imports
def lazy_import(module_path: str, class_name: str):
    """
    Decorator for lazy importing to avoid circular imports.

    Example:
        @lazy_import('myapp.serializers', 'MySerializer')
        def my_view(request):
            MySerializer = lazy_import.get_class()
            # Use MySerializer here
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Inject the class into the function's globals
            cls = resolver.get_class(module_path, class_name)
            func.__globals__[class_name] = cls
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Context manager for temporary imports
class LazyImportContext:
    """
    Context manager for importing classes within a specific scope.

    Example:
        with LazyImportContext() as ctx:
            User = ctx.get_model('auth', 'User')
            MySerializer = ctx.get_serializer('myapp', 'MySerializer')
            # Use them here
    """

    def __init__(self):
        self.resolver = ImportResolver()

    def __enter__(self):
        return self.resolver

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.resolver.clear_cache()


# Usage Examples:

"""
# Example 1: Basic usage in views.py (UPDATED for your case)
from utils.import_resolver import resolver

class MyView(APIView):
    def get(self, request):
        # This should work better with the improved circular import handling
        User = resolver.get_model('auth', 'User')
        
        # For your specific case with ProductListSerializer:
        try:
            ProductListSerializer = resolver.get_serializer('apps.products.product_base', 'ProductListSerializer')
        except ImproperlyConfigured:
            # Fallback approach using lazy import
            ProductListSerializer = resolver.get_class_lazy('apps.products.product_base.serializers', 'ProductListSerializer')()
        
        # Use them here
        users = User.objects.all()
        return Response({'status': 'ok'})

# Example 2: Using the safe circular import handler
from utils.import_resolver import circular_handler

def my_function():
    # This won't raise an exception, returns None if circular import
    ProductListSerializer = circular_handler.get_serializer_safe(
        'apps.products.product_base', 
        'ProductListSerializer'
    )
    
    if ProductListSerializer:
        # Use the serializer
        serializer = ProductListSerializer(data={})
    else:
        # Handle the case when serializer couldn't be imported
        print("Serializer not available due to circular import")

# Example 3: For your specific ProductListSerializer case
from utils.import_resolver import resolver

# Method 1: With fallback modules
try:
    ProductListSerializer = resolver.get_serializer(
        'apps.products.product_base', 
        'ProductListSerializer',
        fallback_modules=[
            'apps.products.product_base.api.serializers',
            'apps.products.serializers'
        ]
    )
except ImproperlyConfigured:
    # Method 2: Lazy loading
    ProductListSerializer = resolver.get_class_lazy(
        'apps.products.product_base.serializers', 
        'ProductListSerializer'
    )

# Example 4: Deferred import pattern
from utils.import_resolver import resolver

class MySerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        # Import only when needed, not at module level
        if hasattr(self, '_ProductListSerializer'):
            ProductListSerializer = self._ProductListSerializer
        else:
            ProductListSerializer = resolver.get_class(
                'apps.products.product_base.serializers', 
                'ProductListSerializer'
            )
            self._ProductListSerializer = ProductListSerializer
        
        # Use ProductListSerializer here
        return super().to_representation(instance)

# Example 5: Breaking circular imports with proper module structure
# In your views.py or wherever you're using it:
from utils.import_resolver import resolver

def get_product_serializer():
    \"\"\"Factory function to get the serializer when needed.\"\"\"
    return resolver.get_class(
        'apps.products.product_base.serializers', 
        'ProductListSerializer'
    )

# Then use it like:
def my_view(request):
    ProductListSerializer = get_product_serializer()
    # Use serializer here
"""

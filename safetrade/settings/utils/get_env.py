import os
import dj_database_url


class EnvHandler:
    """
    A class to handle fetching and casting environment variables.
    """

    def get(self, variable_name, default=None, cast_to=str):
        """
        Gets an environment variable with an optional default, type casting,
        and clear error handling for missing required variables.
        """
        value = os.environ.get(variable_name, default)

        # Raise an error if a required variable is not set (and has no default)
        if value is None:
            raise ValueError(
                f"🚨 Critical setting '{variable_name}' is not set in the environment!"
            )

        # Handle boolean casting
        if cast_to == bool:
            return str(value).lower() in ["true", "1", "t", "yes"]

        # Try to cast the value to the specified type
        try:
            return cast_to(value)
        except (ValueError, TypeError):
            raise TypeError(
                f"Could not cast environment variable '{variable_name}' to {cast_to.__name__}."
            )

    def db(self, variable_name="DATABASE_URL", default=None):
        """
        Fetches a database URL from the environment and parses it into a
        connection dictionary suitable for database clients (e.g., Django, SQLAlchemy).
        """
        # Step 1: Get the database URL string using the generic 'get' method.
        db_url_string = self.get(variable_name, default=default, cast_to=str)

        # Step 2: Parse the URL string into a dictionary.
        # If the string is empty or invalid, it will raise an error.
        return dj_database_url.parse(
            db_url_string,
            conn_max_age=600,
            conn_health_checks=True,
        )


# Create an instance of the handler to use in your application
env = EnvHandler()

# --- HOW TO USE IT ---

# Example 1: Get the database configuration
# It will first look for a "DATABASE_URL" environment variable.
# If not found, it will use the default URL provided.
# db_config = env.db(default="postgres://user:password@host:5432/dbname")

# The 'db_config' variable now holds a dictionary like this:
# {
#     'ENGINE': 'django.db.backends.postgresql',
#     'NAME': 'dbname',
#     'USER': 'user',
#     'PASSWORD': 'password',
#     'HOST': 'host',
#     'PORT': 5432
# }
# print(f"Database Config: {db_config}")


# # Example 2: Get a regular environment variable as an integer
# debug_level = env.get("DEBUG_LEVEL", default=0, cast_to=int)
# print(f"Debug Level: {debug_level}")

# # Example 3: Get a boolean setting
# enable_feature = env.get("ENABLE_FEATURE", default=False, cast_to=bool)
# print(f"Feature Enabled: {enable_feature}")

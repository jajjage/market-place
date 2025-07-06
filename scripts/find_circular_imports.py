# Save this in your project root as e.g., find_circular_imports.py
import os
import ast
from collections import defaultdict
import django  # Import django itself
from django.apps import apps

# from django.conf import settings  # Import settings


def find_project_imports(app_configs, project_root):
    """Finds all internal imports within the project's apps."""
    app_paths = {app.name: app.path for app in app_configs}
    app_names = list(app_paths.keys())
    dependencies = defaultdict(set)

    for app_name, app_path in app_paths.items():
        for root, _, files in os.walk(app_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            # Parse the file into an Abstract Syntax Tree
                            tree = ast.parse(f.read(), filename=file_path)
                            # Find all import statements
                            for node in ast.walk(tree):
                                # Catches "from project.app import ..."
                                if isinstance(node, ast.ImportFrom) and node.module:
                                    module_parts = node.module.split(".")
                                    # Check if the import is from another project app
                                    # We need to handle potential relative imports as well,
                                    # but for top-level app circularity, checking the first part is often sufficient.
                                    # Consider adding more sophisticated path resolution for complex projects.
                                    if (
                                        module_parts[0] in app_names
                                        and module_parts[0] != app_name
                                    ):
                                        dependencies[app_name].add(module_parts[0])
                                # Catches "import project.app"
                                elif isinstance(node, ast.Import):
                                    for alias in node.names:
                                        module_parts = alias.name.split(".")
                                        if (
                                            module_parts[0] in app_names
                                            and module_parts[0] != app_name
                                        ):
                                            dependencies[app_name].add(module_parts[0])
                        except Exception as e:
                            print(f"Could not parse {file_path}: {e}")

    return dependencies


def find_cycles(dependencies):
    """Finds cycles in a dependency graph using Depth First Search."""
    path = set()
    visited = set()
    cycles = []

    def dfs(node):
        path.add(node)
        visited.add(node)
        for neighbor in dependencies.get(node, []):
            if neighbor in path:
                # Cycle detected
                cycle_path = list(path)
                try:
                    # Get the part of the path that forms the cycle
                    cycle_start_index = cycle_path.index(neighbor)
                    cycle = cycle_path[cycle_start_index:] + [neighbor]
                    # Sort to avoid duplicate permutations (e.g., A->B->C and B->C->A)
                    # Using a tuple for the sorted cycle makes it hashable for checking uniqueness
                    sorted_cycle = tuple(sorted(cycle))
                    if sorted_cycle not in [tuple(sorted(c)) for c in cycles]:
                        cycles.append(cycle)
                except ValueError:
                    pass  # Should not happen
                continue
            if neighbor not in visited:
                dfs(neighbor)
        path.remove(node)

    # We need to iterate over all possible nodes in the dependency graph
    # This ensures that even disconnected components or nodes without outgoing edges are considered
    all_nodes = set(dependencies.keys())
    for deps_set in dependencies.values():
        all_nodes.update(deps_set)

    for (
        node
    ) in all_nodes:  # Iterate over all unique app names that appear as keys or values
        if node not in visited:
            dfs(node)

    return cycles


# --- Main execution ---
def find_cycles_command():
    # --- Django Environment Setup ---
    # Set the default settings module for your Django project.
    # IMPORTANT: Replace 'safetrade.settings' with the actual path to your project's settings file.
    # For example, if your project is named 'myproject' and your settings are in 'myproject/settings.py',
    # it would be 'myproject.settings'.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safetrade.settings")

    try:
        django.setup()
    except Exception as e:
        print(f"Error initializing Django: {e}")
        print(
            "Please ensure DJANGO_SETTINGS_MODULE is correctly set and your Django project is valid."
        )
        return 1  # Indicate an error

    print("🔍 Starting circular dependency check...")
    # project_root can be inferred from the settings or passed explicitly if needed
    # For a typical Django project, the project root is where manage.py resides.
    # You might need to adjust this depending on your project structure.
    # A simple way for a script at the project root is:
    project_root = (
        os.getcwd()
    )  # Gets the current working directory, assuming you run from project root

    all_apps = apps.get_app_configs()
    dependencies = find_project_imports(all_apps, project_root)

    print("\nApp Dependencies Found:")
    if not dependencies:
        print("No inter-app dependencies found.")
    else:
        for app, deps in dependencies.items():
            print(f"  - {app} imports: {list(deps)}")

    detected_cycles = find_cycles(dependencies)

    if detected_cycles:
        print("\n🚨 CRITICAL: Circular dependencies detected! 🚨")
        for i, cycle in enumerate(detected_cycles, 1):
            print(f"  Cycle {i}: {' -> '.join(cycle)}")
        return 1  # Indicate that cycles were found
    else:
        print("\n✅ SUCCESS: No circular dependencies found.")
        return 0  # Indicate success


if __name__ == "__main__":
    import sys

    sys.exit(find_cycles_command())

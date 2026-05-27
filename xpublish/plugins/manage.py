"""Load and configure Xpublish plugins from entry point group `xpublish.plugin`."""

from collections.abc import Iterable
from importlib.metadata import entry_points

from .hooks import Plugin


def find_default_plugins(
    exclude_plugins: Iterable[str] | None = None,
) -> dict[str, type[Plugin]]:
    """Find Xpublish plugins from entry point group `xpublish.plugin`.

    Args:
        exclude_plugins: A list of plugin names to ignore.

    Returns:
        A dictionary of plugin names and classes.
    """
    exclude_plugins = set(exclude_plugins or [])

    plugins: dict[str, type[Plugin]] = {}

    plugin_entry_points = entry_points(group='xpublish.plugin')

    for entry_point in plugin_entry_points:
        if entry_point.name not in exclude_plugins:
            plugins[entry_point.name] = entry_point.load()

    return plugins


def load_default_plugins(
    exclude_plugins: Iterable[str] | None = None,
) -> dict[str, Plugin]:
    """Find and initialize plugins from entry point group `xpublish.plugin`.

    Args:
        exclude_plugins: A list of plugin names to ignore.

    Returns:
        A dictionary of plugin names and instances.
    """
    initialized_plugins: dict[str, Plugin] = {}

    for name, plugin in find_default_plugins(exclude_plugins=exclude_plugins).items():
        initialized_plugins[name] = plugin()

    return initialized_plugins


def configure_plugins(
    plugins: dict[str, type[Plugin]],
    plugin_configs: dict[str, dict] | None = None,
) -> dict[str, Plugin]:
    """Initialize and configure plugins with given dictionary of configurations.

    Args:
        plugins: A dictionary of plugin names and classes.
        plugin_configs: A dictionary of plugin names and configurations.

    Returns:
        A dictionary of plugin names and instances.
    """
    initialized_plugins: dict[str, Plugin] = {}
    plugin_configs = plugin_configs or {}

    for name, plugin in plugins.items():
        kwargs = plugin_configs.get(name, {})
        initialized_plugins[name] = plugin(**kwargs)

    return initialized_plugins

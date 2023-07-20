"""
Load and configure Xpublish plugins from entry point group `xpublish.plugin`
"""
from importlib.metadata import entry_points
from typing import Dict, Iterable, Optional, Type

from .hooks import Plugin


def find_default_plugins(
    exclude_plugins: Optional[Iterable[str]] = None,
) -> Dict[str, Type[Plugin]]:
    """Find Xpublish plugins from entry point group `xpublish.plugin`

    Individual plugins may be ignored by adding them to `exclude_plugins`.
    """
    exclude_plugins = set(exclude_plugins or [])

    plugins: Dict[str, Type[Plugin]] = {}

    for entry_point in entry_points()['xpublish.plugin']:
        if entry_point.name not in exclude_plugins:
            plugins[entry_point.name] = entry_point.load()

    return plugins


def load_default_plugins(
    exclude_plugins: Optional[Iterable[str]] = None,
) -> Dict[str, Plugin]:
    """Find and initialize plugins from entry point group `xpublish.plugin`"""
    initialized_plugins: Dict[str, Plugin] = {}

    for name, plugin in find_default_plugins(exclude_plugins=exclude_plugins).items():
        initialized_plugins[name] = plugin()

    return initialized_plugins


def configure_plugins(
    plugins: Dict[str, Type[Plugin]],
    plugin_configs: Optional[Dict] = None,
) -> Dict[str, Plugin]:
    """Initialize and configure plugins with given dictionary of configurations"""
    initialized_plugins: Dict[str, Plugin] = {}
    plugin_configs = plugin_configs or {}

    for name, plugin in plugins.items():
        kwargs = plugin_configs.get(name, {})
        initialized_plugins[name] = plugin(**kwargs)

    return initialized_plugins

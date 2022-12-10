"""
Load and configure Xpublish plugins from entry point group `xpublish.plugin`
"""
from importlib.metadata import entry_points
from typing import Dict, List, Optional

from .factory import XpublishPluginFactory


def find_plugins(exclude_plugins: Optional[List[str]] = None):
    """Find Xpublish plugins from entry point group `xpublish.plugin`"""
    exclude_plugin_names = set(exclude_plugins or [])

    plugins: Dict[str, XpublishPluginFactory] = {}

    for entry_point in entry_points()['xpublish.plugin']:
        if entry_point.name not in exclude_plugin_names:
            plugins[entry_point.name] = entry_point.load()

    return plugins


def configure_plugins(
    plugins: Dict[str, XpublishPluginFactory], plugin_configs: Optional[Dict] = None
):
    """Initialize and configure plugins"""
    initialized_plugins: Dict[str, XpublishPluginFactory] = {}
    plugin_configs = plugin_configs or {}

    for name, plugin in plugins.items():
        kwargs = plugin_configs.get(name, {})
        initialized_plugins[name] = plugin(**kwargs)

    return initialized_plugins

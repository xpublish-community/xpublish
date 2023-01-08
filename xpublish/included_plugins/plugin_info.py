"""
Plugin information router
"""
import importlib
from typing import Dict, Optional

from fastapi import Depends
from pydantic import BaseModel, Field

from ..plugin import Plugin, Router


class PluginInfo(BaseModel):
    path: str
    version: Optional[str]


class PluginInfoAppRouter(Router):
    """Plugin information"""

    prefix = ''

    def register(self):
        @self._router.get('/plugins')
        def get_plugins(
            plugins: dict[str, Plugin] = Depends(self.deps.plugins)
        ) -> Dict[str, PluginInfo]:
            plugin_info = {}

            for name, plugin in plugins.items():
                plugin_type = type(plugin)
                module_name = plugin_type.__module__.split('.')[0]
                try:
                    mod = importlib.import_module(module_name)
                    version = getattr(mod, '__version__', None)
                except ImportError:
                    version = None

                plugin_info[name] = PluginInfo(
                    path=f'{plugin_type.__module__}.{plugin.__repr_name__()}', version=version
                )

            return plugin_info


class PluginInfoPlugin(Plugin):
    name = 'plugin_info'

    app_router: PluginInfoAppRouter = Field(default_factory=PluginInfoAppRouter)

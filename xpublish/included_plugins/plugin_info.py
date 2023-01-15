"""
Plugin information router
"""
import importlib
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..plugin import Plugin, hookimpl


class PluginInfo(BaseModel):
    path: str
    version: Optional[str]


class PluginInfoPlugin(Plugin):
    name = 'plugin_info'

    app_router_prefix: str = ''
    app_router_tags: List[str] = []

    @hookimpl
    def app_router(self):
        router = APIRouter(prefix=self.app_router_prefix, tags=self.app_router_tags)

        @router.get('/plugins')
        def get_plugins(
            plugins: Dict[str, Plugin] = Depends(self.dependencies.plugins)
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

        return router

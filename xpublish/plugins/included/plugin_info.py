"""
Plugin information router
"""
import importlib
from typing import Dict, Optional, Sequence

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import Dependencies, Plugin, hookimpl


class PluginInfo(BaseModel):
    path: str
    version: Optional[str] = None


class PluginInfoPlugin(Plugin):
    """Expose plugin source and version"""

    name: str = 'plugin_info'

    app_router_prefix: str = ''
    app_router_tags: Sequence[str] = ['plugin_info']

    @hookimpl
    def app_router(self, deps: Dependencies) -> APIRouter:
        router = APIRouter(
            prefix=self.app_router_prefix,
            tags=list(self.app_router_tags),
        )

        @router.get('/plugins')
        def get_plugins(
            plugins: Dict[str, Plugin] = Depends(deps.plugins)
        ) -> Dict[str, PluginInfo]:
            """Return the source and version of the currently loaded plugins"""
            plugin_info = {}

            for name, plugin in plugins.items():
                plugin_type = type(plugin)
                module_name = plugin_type.__module__.split('.')[0]
                try:
                    mod = importlib.import_module(module_name)
                    version = getattr(mod, '__version__', None)
                except ImportError:  # pragma: no cover
                    version = None  # pragma: no cover

                plugin_info[name] = PluginInfo(
                    path=f'{plugin_type.__module__}.{plugin.__repr_name__()}',
                    version=version,
                )

            return plugin_info

        return router

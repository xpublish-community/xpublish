from typing import Any, Callable, List, Optional

import cachey
import xarray as xr
from fastapi import APIRouter
from pydantic import BaseModel, Field, PrivateAttr

from ..dependencies import get_cache, get_dataset, get_dataset_ids, get_plugins


class PluginDependencies(BaseModel):
    dataset_ids: Callable[..., List[str]] = get_dataset_ids
    dataset: Callable[..., xr.Dataset] = get_dataset
    cache: Callable[..., cachey.Cache] = get_cache
    plugins: Callable[..., 'Plugin'] = get_plugins


class Plugin(BaseModel):
    """
    Xpublish plugins provide ways to extend the core of xpublish with
    new routers and other functionality.

    To create a plugin, subclass ``Plugin` and add attributes that are
    subclasses of `PluginType` (`Router` for instance).

    The specific attributes correspond to how Xpublish should use
    the plugin.
    """

    name: str
    dependencies: PluginDependencies = Field(
        default_factory=PluginDependencies,
        description='Xpublish dependencies, which can be overridden on a per-plugin basis',
    )

    app_router: Optional['Router'] = Field(
        description='Top level routes that are not dependent on specific datasets'
    )
    dataset_router: Optional['Router'] = Field(
        description='Routes that are dependent on specific datasets'
    )

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.set_parent()
        self.register()

    def register(self):
        """Setup routes and other plugin functionality"""
        for extension in self.iter_extensions():
            extension.register()

    def iter_extensions(self):
        """Iterate over all types of plugins that the plugin supports"""
        for key in self.dict():
            attr = getattr(self, key)

            if isinstance(attr, PluginType):
                yield attr

    def _parent(self):
        """Secret helper method to allow extensions to access the parent plugin without
        ending up in a recursive loop"""
        return self

    def set_parent(self):
        """
        Set the parent attribute on extensions to allow them to access attributes
        from other parts of plugins
        """
        for extension in self.iter_extensions():
            extension._parent = self._parent


class PluginType(BaseModel):
    """A base class for various plugin functionality to be built off of.

    This helps provide access to the parent class, and dependencies.

    Subclasses need to reimplement the `register()` method to enable
    their functionality.
    """

    _parent: Optional[Callable[[], Plugin]] = PrivateAttr()

    @property
    def plugin(self):
        """Access the plugin from an extension"""
        return self._parent()

    @property
    def deps(self):
        """Access the dependencies of plugin"""
        return self.plugin.dependencies

    def register(self):
        """Implement for any plugin functionality that requires setup.

        If no setup is needed, re-implement and pass to avoid errors.
        """
        raise NotImplementedError


class Router(PluginType):
    """Base class used by plugins implementing new routes.

    Subclass Router, and create routes by re-implementing `register()` with
    using `@self._router.METHOD()` on nested functions.
    """

    prefix: str = Field(description='Shared route prefix')
    tags: list[str] = Field(default_factory=list, description='Tags in OpenAPI documentation')

    _router: APIRouter = PrivateAttr(default_factory=APIRouter)

    def register(self):
        """Register API Routes"""
        raise NotImplementedError

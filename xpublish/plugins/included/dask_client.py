"""
Default Dask clients
"""
from dask import distributed
from pydantic import Field

from .. import Plugin, hookimpl


class DaskClientPlugin(Plugin):
    name = 'dask_client'

    sync_kwargs: dict = Field(
        default_factory=dict, description='Keyword arguments for syncronous Dask distributed.Client'
    )
    async_kwargs: dict = Field(
        default_factory=dict,
        description='Keyword arguments for asyncronous Dask distributed.Client',
    )

    @hookimpl(trylast=True)
    def get_dask_sync_client(self, cluster: distributed.SpecCluster):
        client = distributed.Client(cluster, **self.sync_kwargs)

        return client

    @hookimpl(trylast=True)
    def get_dask_async_client(self, cluster: distributed.SpecCluster):
        client = distributed.Client(cluster, asynchronous=True, **self.async_kwargs)

        return client

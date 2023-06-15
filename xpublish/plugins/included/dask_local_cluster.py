"""
Default Dask local cluster
"""
from dask import distributed

from .. import Plugin, hookimpl


class DaskLocalClusterPlugin(Plugin):
    name = 'dask_local_cluster'

    @hookimpl(trylast=True)
    def get_dask_cluster(self):
        """Creates a local Dask cluster"""
        try:
            return self._cluster
        except AttributeError:
            cluster = distributed.LocalCluster()
            self._cluster = cluster
            return cluster

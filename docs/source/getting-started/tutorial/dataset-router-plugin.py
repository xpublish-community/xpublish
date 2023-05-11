import xarray as xr
from fastapi import APIRouter, Depends, HTTPException

from xpublish import Dependencies, Plugin, SingleDatasetRest, hookimpl


class MeanPlugin(Plugin):
    name = 'mean'

    dataset_router_prefix = ''
    dataset_router_tags = ['mean']

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get('/{var_name}/mean')
        def get_mean(var_name: str, dataset=Depends(deps.dataset)):
            if var_name not in dataset.variables:
                raise HTTPException(
                    status_code=404,
                    detail=f"Variable '{var_name}' not found in dataset",
                )

            return float(dataset[var_name].mean())

        return router


ds = xr.tutorial.open_dataset(
    'air_temperature',
    chunks={'lat': 5, 'lon': 5},
)

rest = SingleDatasetRest(ds)
rest.register_plugin(MeanPlugin())
rest.serve()

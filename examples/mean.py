from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException

from xpublish import Plugin,  hookimpl, Dependencies


class MeanPlugin(Plugin):
    name: str = 'mean'

    dataset_router_prefix: str = ''
    dataset_router_tags: Sequence[str] = ['mean']

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
            
            mean = dataset[var_name].mean()
            if mean.isnull():
                return "NaN"
            return float(mean)

        return router

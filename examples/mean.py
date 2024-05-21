from typing import Sequence
from fastapi import APIRouter, Depends, HTTPException
from xpublish import Plugin, hookimpl, Dependencies


class MeanPlugin(Plugin):
    """
    Provides a plugin that adds a dataset router for computing the mean of variables in a dataset.

    The `MeanPlugin` class defines the following:
    - `name`: The name of the plugin, set to 'mean'.
    - `dataset_router_prefix`: The prefix for the dataset router, set to an empty string.
    - `dataset_router_tags`: The tags for the dataset router, set to ['mean'].

    The `dataset_router` method creates an APIRouter with the defined prefix and tags, and adds a GET endpoint for computing the mean of a variable in the dataset. If the variable is not found in the dataset, an HTTPException is raised with a 404 status code.
    """

    name: str = "mean"

    dataset_router_prefix: str = ""
    dataset_router_tags: Sequence[str] = ["mean"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get("/{var_name}/mean")
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

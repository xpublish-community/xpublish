# Building a dataset router

It is also possible to create custom API routes and serve them via Xpublish. In
the example below, we create a minimal application to get the mean value of a
given variable in the published dataset:

```python
from fastapi import APIRouter, Depends, HTTPException
from xpublish.dependencies import get_dataset


myrouter = APIRouter()


@myrouter.get("/{var_name}/mean")
def get_mean(var_name: str, dataset: xr.Dataset = Depends(get_dataset)):
    if var_name not in dataset.variables:
        raise HTTPException(
            status_code=404, detail=f"Variable '{var_name}' not found in dataset"
        )

    return float(dataset[var_name].mean())


ds.rest(routers=[myrouter])

ds.rest.serve()
```

Taking the dataset loaded above in this tutorial, this application should behave
like this:

- `/air/mean` returns a floating number
- `/not_a_variable/mean` returns a 404 HTTP error

The {func}`~xpublish.dependencies.get_dataset` function in the example above is
a FastAPI dependency that is used to access the dataset object being served by
the application, either from inside a FastAPI path operation decorated function
or from another FastAPI dependency. Note that `get_dataset` can only be used
as a function argument (FastAPI has other ways to reuse a dependency, but those
are not supported in this case).

Xpublish also provides a {func}`~xpublish.dependencies.get_cache` dependency
function to get/put any useful key-value pair from/into the cache that is
created along with a running instance of the application.

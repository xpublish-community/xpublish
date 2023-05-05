# Extending Xpublish with a dataset router

It is also possible to create custom API routes and serve them via Xpublish. In
the example below, we create a minimal application to get the mean value of a
given variable in the published dataset:

```python
from fastapi import APIRouter, Depends, HTTPException
import xarray as xr
import xpublish
from xpublish.dependencies import get_dataset

ds = xr.tutorial.open_dataset(
    "air_temperature",
    chunks=dict(lat=5, lon=5),
)

myrouter = APIRouter()


@myrouter.get("/{var_name}/mean")
def get_mean(var_name: str, dataset: xr.Dataset = Depends(get_dataset)):
    if var_name not in dataset.variables:
        raise HTTPException(
            status_code=404, detail=f"Variable '{var_name}' not found in dataset"
        )

    return float(dataset[var_name].mean())


rest = ds.rest(routers=[myrouter])

rest.serve()
```

Taking the dataset loaded above in this tutorial, this application should behave
like this:

- `/air/mean` returns a floating number
- `/not_a_variable/mean` returns a 404 HTTP error

## Building blocks of new routes

Adding a new route for a dataset starts with creating a [FastAPI `APIRouter`](https://fastapi.tiangolo.com/tutorial/bigger-applications/#apirouter), which we have done here with `myrouter = APIRouter()`.

Next we define our route using a decorator for the type of request, in this case `@myrouter.get()`.
Within the decorator we specify the path we want the route to respond to.
If we want it to [respond to parameters](https://fastapi.tiangolo.com/tutorial/path-params/) in the path, we can enclose those with curly brackets and they will be passed to our route function.
Here we have specified that we want a path parameter of `var_name` to be passed to the function, and the requests should respond to `{var_name}/mean`.

Following the decorator, we have our function to respond to the route.
It takes in the path parameters, and some other arguments.

The {func}`~xpublish.dependencies.get_dataset` function in the example above is
a [FastAPI dependency](https://fastapi.tiangolo.com/tutorial/dependencies/) that is used to access the dataset object being served by
the application, either from inside a FastAPI path operation decorated function
or from another FastAPI dependency. Note that `get_dataset` can only be used
as a function argument (FastAPI has other ways to reuse a dependency, but those
are not supported in this case).

Xpublish also provides a {func}`~xpublish.dependencies.get_cache` dependency
function to get/put any useful key-value pair from/into the cache that is
created along with a running instance of the application.

To use our route, we then need to tell Xpublish about it, by passing it into `ds.rest`.

Finally we can serve our new route along with the other routes that Xpublish understands.

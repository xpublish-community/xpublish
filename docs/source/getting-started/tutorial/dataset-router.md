# Extending Xpublish with a dataset router

It is also possible to create custom API routes and serve them via Xpublish. In
the example below, we create a minimal application to get the mean value of a
given variable in the published dataset:

```{literalinclude} dataset-router.py
```

Taking the dataset loaded above in this tutorial, this application should behave
like this:

- `/air/mean` returns a floating number
- `/not_a_variable/mean` returns a 404 HTTP error

## Building blocks of new routes

Adding a new route for a dataset starts with creating a [FastAPI `APIRouter`](https://fastapi.tiangolo.com/tutorial/bigger-applications/#apirouter), which we have done here with `myrouter = APIRouter()`.

```{literalinclude} dataset-router.py
---
lines: 6-15
emphasize-lines: 6
---
```

Next we define our route using a decorator for the type of request, in this case `@myrouter.get()`.
Within the decorator we specify the path we want the route to respond to.
If we want it to [respond to parameters](https://fastapi.tiangolo.com/tutorial/path-params/) in the path, we can enclose those with curly brackets and they will be passed to our route function.
Here we have specified that we want a path parameter of `var_name` to be passed to the function, and the requests should respond to `{var_name}/mean`.

```{literalinclude} dataset-router.py
---
lines: 11-19
emphasize-lines: 4
---
```

Following the decorator, we have our function to respond to the route.
It takes in the path parameters, and some other arguments.

```{literalinclude} dataset-router.py
---
lines: 14-22
emphasize-lines: 2-6
---
```

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

```{literalinclude} dataset-router.py
---
lines: 14-24
emphasize-lines: 9,11
---
```

Finally we can serve our new route along with the other routes that Xpublish understands.

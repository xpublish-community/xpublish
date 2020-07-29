========
Tutorial
========

Server-Side
-----------

Xpublish provides a simple accessor interface to serve xarray objects.

To begin, import xpublish and open an xarray dataset:

.. ipython:: python

    import xarray as xr
    import xpublish

    ds = xr.tutorial.open_dataset(
        "air_temperature", chunks=dict(lat=5, lon=5),
    )

Optional customization of the underlying
`FastAPI application <https://fastapi.tiangolo.com>`_ or the server-side
`cache <https://github.com/dask/cachey>`_ is possible when the accessor
is initialized:

.. ipython:: python

    ds.rest(
        app_kws=dict(
            title="My Dataset",
            description="Dataset Description",
            openapi_url="/dataset.JSON",
        ),
        cache_kws=dict(available_bytes=1e9)
    )

Serving a dataset simply requires calling the `serve` method on the `rest`
accessor:

.. ipython:: python
    :verbatim:

    ds.rest.serve()

`serve()` passes any keyword arguments on to `uvicorn.run`.

Default API routes
~~~~~~~~~~~~~~~~~~

By default, the served application provides the following endpoints to get some
information about the published dataset:

* ``/``: returns xarray's HTML repr.
* ``/keys``: returns a list of variable keys, equivalent to ``list(ds.variables)``.
* ``/info``: returns a JSON dictionary summary of a Dataset variables and attributes, similar to ``ds.info()``.
* ``/dict``: returns a JSON dictionary of the full dataset.
* ``/versions``: returns JSON dictionary of the versions of python, xarray and related libraries on the server side, similar to ``xr.show_versions()``.

The application also provides data access through a Zarr compatible API with the
following endpoints:

* ``/.zmetadata``: returns a JSON dictionary representing the consolidated Zarr metadata.
* ``/{var}/{key}``: returns a single chunk of an array.

Custom API routes
~~~~~~~~~~~~~~~~~

With Xpublish you have full control on which/how API endpoints are exposed by
the application.

In the example below, the default API routes are included with additional tags
and using a path prefix for zarr-like data access:

.. code-block:: python

   from xpublish.routers import base_router, common_router, zarr_router

   ds.rest(
       routers=[
           (base_router, {'tags': 'info'}),
           (common_router, {'tags': 'info'}),
           (zarr_router, {'tags': 'data', 'prefix': '/data'})
       ]
   )

   ds.rest.serve()

Using those settings, Zarr API endpoints now have the following paths:

* ``/data/.zmetadata``
* ``/data/{var}/{key}``

It is also possible to create custom API routes and serve them via the
application. In the example below, we create a very minimal application to get
the mean value of a given variable in the published dataset:

.. code-block:: python

   from fastapi import APIRouter, Depends, HTTPException
   from xpublish.dependencies import get_dataset

   myrouter = APIRouter()

   @myrouter.get("{var_name}/mean")
   def get_mean(dataset: xr.Dataset = Depends(get_dataset), var_name: str):
       if var_name not in dataset.variables:
           raise HTTPException(
               status_code=404, detail=f"Variable {var_name} not found in dataset"
           )

       return dataset[var_name].mean().item()

   ds.rest(routers=[myrouter])

   ds.rest.serve()

Taking the dataset loaded above in this tutorial, this minimal application
should like this:

* ``/air/mean`` returns a floating number
* ``/not_a_variable/mean`` returns a 404 HTTP error

The ``get_dataset`` function in the example above is a FastAPI dependency that
is used to access the dataset object being served by the application from inside
a FastAPI path operation decorated function or another FastAPI dependency. Note
that ``get_dataset`` can only be used as function arguments.

Xpublish also provides a ``get_cache`` dependency function to get/put any useful
key/value pair from/into the cache that is created along with a running instance
of the application.

API Docs
~~~~~~~~

Thanks to FastAPI and `Swagger UI`_, automatically generated
interactive documentation is available at the ``/docs`` URL.

This path can be overridden by setting the ``docs_url`` key in the ``app_kws``
dictionary argument when initializing the rest accessor.

.. _`Swagger UI`: https://github.com/swagger-api/swagger-ui

Client-Side
-----------

Datasets served by xpublish are can be opened by any zarr client that
implements an HTTPStore. In Python, this can be done with fsspec:

.. ipython:: python
    :verbatim:

    import zarr
    from fsspec.implementations.http import HTTPFileSystem

    fs = HTTPFileSystem()
    http_map = fs.get_mapper('http://0.0.0.0:9000')

    # open as a zarr group
    zg = zarr.open_consolidated(http_map, mode='r')

    # or open as another xarray dataset
    ds = xr.open_zarr(http_map, consolidated=True)

Xpublish's endpoints can also be queried programmatically. For example:

.. ipython:: python
    :verbatim:

    import requests

    response = requests.get('http://0.0.0.0:9000/info').json()

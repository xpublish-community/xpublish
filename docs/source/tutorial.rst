========
Tutorial
========

Server-Side
-----------

To begin, import Xpublish and open an Xarray dataset:

.. code-block:: python

    import xarray as xr
    import xpublish

    ds = xr.tutorial.open_dataset(
        "air_temperature", chunks=dict(lat=5, lon=5),
    )

Publishing the dataset above is straightforward, just use the
:class:`~xpublish.Rest` class:

.. code-block:: python

   rest = xpublish.Rest(ds)

Alternatively, you might want to use the :attr:`xarray.Dataset.rest` accessor
for more convenience:

.. code-block:: python

    ds.rest

Optional customization of the underlying `FastAPI
application <https://fastapi.tiangolo.com>`_ or the server-side `cache
<https://github.com/dask/cachey>`_ is possible, e.g.,

.. code-block:: python

    ds.rest(
        app_kws=dict(
            title="My Dataset",
            description="Dataset Description",
            openapi_url="/dataset.JSON",
        ),
        cache_kws=dict(available_bytes=1e9)
    )

Serving the dataset then simply requires calling the :meth:`~Rest.serve` method
on the ``Rest`` instance or the ``rest`` accessor:

.. code-block:: python

    rest.serve()

    # or

    ds.rest.serve()

:meth:`~xarray.Dataset.rest.serve` passes any keyword arguments on to
:func:`uvicorn.run`.

Default API routes
~~~~~~~~~~~~~~~~~~

By default, the FastAPI application created with Xpublish provides the following
endpoints to get some information about the published dataset:

* ``/``: returns xarray's HTML repr.
* ``/keys``: returns a list of variable keys, i.e., those returned by :attr:`xarray.Dataset.variables`.
* ``/info``: returns a JSON dictionary summary of a Dataset variables and attributes, similar to :meth:`xarray.Dataset.info`.
* ``/dict``: returns a JSON dictionary of the full dataset.
* ``/versions``: returns JSON dictionary of the versions of python, xarray and related libraries on the server side, similar to :func:`xarray.show_versions`.

The application also provides data access through a Zarr compatible API with the
following endpoints:

* ``/.zmetadata``: returns a JSON dictionary representing the consolidated Zarr metadata.
* ``/{var}/{key}``: returns a single chunk of an array.

Custom API routes
~~~~~~~~~~~~~~~~~

With Xpublish you have full control on which and how API endpoints are exposed
by the application.

In the example below, the default API routes are included with custom tags
and using a path prefix for Zarr-like data access:

.. code-block:: python

   from xpublish.routers import base_router, zarr_router

   ds.rest(
       routers=[
           (base_router, {'tags': 'info'}),
           (zarr_router, {'tags': 'zarr', 'prefix': '/zarr'})
       ]
   )

   ds.rest.serve()

Using those settings, the Zarr-specific API endpoints now have the following
paths:

* ``/zarr/.zmetadata``
* ``/zarr/{var}/{key}``

It is also possible to create custom API routes and serve them via Xpublish. In
the example below, we create a minimal application to get the mean value of a
given variable in the published dataset:

.. code-block:: python

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

Taking the dataset loaded above in this tutorial, this application should behave
like this:

* ``/air/mean`` returns a floating number
* ``/not_a_variable/mean`` returns a 404 HTTP error

The :func:`~xpublish.dependencies.get_dataset` function in the example above is
a FastAPI dependency that is used to access the dataset object being served by
the application, either from inside a FastAPI path operation decorated function
or from another FastAPI dependency. Note that ``get_dataset`` can only be used
as function arguments.

Xpublish also provides a :func:`~xpublish.dependencies.get_cache` dependency
function to get/put any useful key-value pair from/into the cache that is
created along with a running instance of the application.

API Docs
~~~~~~~~

Thanks to FastAPI and `Swagger UI`_, automatically generated
interactive documentation is available at the ``/docs`` URL.

This path can be overridden by setting the ``docs_url`` key in the ``app_kws``
dictionary argument when initializing the rest accessor.

.. _`Swagger UI`: https://github.com/swagger-api/swagger-ui

Serving multiple datasets
~~~~~~~~~~~~~~~~~~~~~~~~~

Xpublish also lets you serve multiple datasets via one FastAPI application. You
just need to provide a mapping (dictionary) when creating a
:class:`~xpublish.Rest` instance, e.g.,

.. code-block:: python

    ds2 = xr.tutorial.open_dataset('rasm')

    rest_collection = xpublish.Rest({'air_temperature': ds, 'rasm': ds2})

    rest_collection.serve()

When multiple datasets are given, all dataset-specific API endpoint URLs have
the ``/datasets/{dataset_id}`` prefix. For example:

* ``/datasets/rasm/info`` returns information about the ``rasm`` dataset
* ``/datasets/invalid_dataset_id/info`` returns a 404 HTTP error

The application has also one more API endpoint:

* ``/datasets``: returns the list of the ids (keys) of all published datasets

Note that custom routes work for multiple datasets just as well as for a single
dataset, no code change is required. Taking the example above,

.. code-block:: python

    rest_collection = xpublish.Rest(
        {'air_temperature': ds, 'rasm': ds2},
        routers=[myrouter]
    )

    rest_collection.serve()

The following URLs should return expected results:

* ``/datasets/air_temperature/air/mean``
* ``/datasets/rasm/Tair/mean``

Client-Side
-----------

By default, datasets served by Xpublish are can be opened by any Zarr client
that implements an HTTPStore. In Python, this can be done with ``fsspec``:

.. code-block:: python

    import zarr
    from fsspec.implementations.http import HTTPFileSystem

    fs = HTTPFileSystem()

    # The URL 'http://0.0.0.0:9000' here serves one dataset
    http_map = fs.get_mapper('http://0.0.0.0:9000')

    # open as a zarr group
    zg = zarr.open_consolidated(http_map, mode='r')

    # or open as another xarray dataset
    ds = xr.open_zarr(http_map, consolidated=True)

Xpublish's endpoints can also be queried programmatically. For example:

.. code-block:: python

    import requests

    response = requests.get('http://0.0.0.0:9000/info').json()

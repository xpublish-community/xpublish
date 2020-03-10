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

Once launched, the server provides the following endpoints:

REST API
~~~~~~~~

* ``/``: returns xarray's HTML repr.
* ``/keys``: returns a list of variable keys, equivalent to ``list(ds.variables)``.
* ``/info``: returns a JSON dictionary summary of a Dataset variables and attributes, similar to ``ds.info()``.
* ``/dict``: returns a JSON dictionary of the full dataset.
* ``/versions``: returns JSON dictionary of the versions of python, xarray and related libraries on the server side, similar to ``xr.show_versions()``.

Zarr API
~~~~~~~~

* ``/.zmetadata``: returns a JSON dictionary representing the consolidated Zarr metadata.
* ``/{var}/{key}``: returns a single chunk of an array.

API Docs
~~~~~~~~

* ``/docs``: Interactive Swagger UI API documentation. This can be set with ``docs_url`` parameter when initializing application.

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

    In [1]: import requests

    In [2]: response = requests.get('http://0.0.0.0:9000/info').json()

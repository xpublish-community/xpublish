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

Optional customization of the underlying FastAPI application is available by using the ``init_app`` method before running ``serve`` below:

.. ipython:: python

    ds.rest.init_app(
        title="My Dataset",
        description="Dataset Description",
        version="1.0.0",
        openapi_url="/dataset.json",
        docs_url="/data-docs"
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
* ``/info``: returns a concise summary of a Dataset variables and attributes, equivalent to ``ds.info()``.
* ``/dict``: returns a json dictionary of the full dataset. Accpets the ``?data={value}`` parameter to specify if the return dictionary should include the data in addition to the dataset schema.
* ``/versions``: returns a plain text summary of the versions of xarray and related libraries on the server side, equivalent to ``xr.show_versions()``.

Zarr API
~~~~~~~~

* ``/.zmetadata``: returns a json dictionary representing the consolidated Zarr metadata.
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

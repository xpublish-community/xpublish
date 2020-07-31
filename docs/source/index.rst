========
xpublish
========

**Xpublish lets you easily publish Xarray datasets via a REST API.**

*You can run a short example application in a live session here:* |Binder|

.. |Binder| image:: https://mybinder.org/badge_logo.svg
 :target: https://mybinder.org/v2/gh/xarray-contrib/xpublish/master

On the server-side, datasets are published using a simple Xarray accessor:

.. code-block:: python

    ds.rest.serve(host="0.0.0.0", port=9000)

Datasets can be accessed from various kinds of client applications, e.g., from
within Python using Zarr and fsspec.

.. code-block:: python

    import xarray as xr
    import zarr
    from fsspec.implementations.http import HTTPFileSystem

    fs = HTTPFileSystem()
    http_map = fs.get_mapper('http://0.0.0.0:9000')

    # open as a zarr group
    zg = zarr.open_consolidated(http_map, mode='r')

    # or open as another xarray dataset
    ds = xr.open_zarr(http_map, consolidated=True)

Why?
~~~~

xpublish lets you serve, share and publish xarray datasets via a web
application.

The data and/or metadata in the xarray datasets can be exposed in various forms
through pluggable REST API endpoints. Efficient, on-demand delivery of large
datasets may be enabled with Dask on the server-side.

We are exploring applications of xpublish that include:

* publish on-demand or derived data products
* turning xarray objects into streaming services (e.g. OPENDAP)

How?
~~~~

Under the hood, xpublish is using a web app (FastAPI and Uvicorn) that is
exposing a REST-like API with builtin and/or user-defined endpoints.

For example, xpublish provides by default a minimal Zarr compatible REST-like
API with the following endpoints:

* ``/.zmetadata``: returns Zarr-formatted metadata keys as json strings.
* ``/var/0.0.0``: returns a variable data chunk as a binary string.

.. toctree::
   :maxdepth: 2
   :caption: Documentation Contents

   installation
   tutorial
   api
   contributing

Feedback
--------

If you encounter any errors or problems with **xpublish**, please open an issue
at the GitHub `main repository <http://github.com/xarray-contrib/xpublish>`_.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

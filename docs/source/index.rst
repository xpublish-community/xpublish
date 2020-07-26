========
xpublish
========

**Xpublish lets you publish Xarray datasets via a Zarr-compatible REST API.**

*You can run a short example application in a live session here:* |Binder|

.. |Binder| image:: https://mybinder.org/badge_logo.svg
 :target: https://mybinder.org/v2/gh/xarray-contrib/xpublish/master

On the server-side, datasets are published using a simple Xarray accessor:

.. code-block:: python

    ds.rest.serve(host="0.0.0.0", port=9000)

On the client-side, datasets are accessed using Zarr and fsspec.

.. ipython:: python
    :verbatim:

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

Xpublish lets you share, publish, and serve Xarray datasets via a web application.
The data in the Xarray datasets (on the server side) can be backed by dask to
facilitate on-demand computation via a simple REST API.

We are exploring applications of xpublish that include:

- publish on-demand or derived data products
- turning Xarray objects into streaming services (e.g. OPENDAP)

How?
~~~~

Under the hood, xpublish is using a web app (FastAPI and Uvicorn) that is
exposing a minimal Zarr compatible REST-like API.

Key attributes of the API are:

- serves a Zarr store API from the root of the dataset.
- provides Zarr metadata keys (``.zmetadata``, ``.zgroup``, ``.zarray``, and ``.zattrs``) as a JSON strings.
- provides access to data keys (e.g. ``var/0.0.0``) as binary strings.

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

xpublish
========

Publish Xarray Datasets via a Zarr compatible REST API

.. image:: https://img.shields.io/github/workflow/status/xarray-contrib/xpublish/CI?logo=github
   :target: https://github.com/xarray-contrib/xpublish/actions?query=workflow%3ACI
   :alt: GitHub Workflow Status

.. image:: https://readthedocs.org/projects/xpublish/badge/?version=latest
   :target: https://xpublish.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://mybinder.org/badge_logo.svg
   :target: https://mybinder.org/v2/gh/xarray-contrib/xpublish/master
   :alt: Binder

.. image:: https://codecov.io/gh/xarray-contrib/xpublish/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/xarray-contrib/xpublish

**Serverside: Publish a xarray dataset as a rest API**

.. code-block:: python

   ds.rest.serve(host="0.0.0.0", port=9000)


**Client-side: Connect to a published dataset**

.. code-block:: python

   import xarray as xr
   import zarr
   from fsspec.implementations.http import HTTPFileSystem

   fs = HTTPFileSystem()
   http_map = fs.get_mapper('http://0.0.0.0:9000')

   # open as a zarr group
   zg = zarr.open_consolidated(http_map, mode='r')

   # open as another xarray dataset
   ds = xr.open_zarr(http_map, consolidated=True)


Why?
^^^^

xpublish lets you serve/share/publish xarray datasets via a web application.
The data in the xarray datasets (on the server side) can be backed by dask to facilitate on-demand computation via a simple REST API.
We are exploring applications of xpublish that include:

* publish on-demand derived data products
* turning xarray objects into streaming services (e.g. OPENDAP)

How?
^^^^

Under the hood, xpublish is using a web app (FastAPI) that is exposing a minimal Zarr compatible REST-like API.
Key attributes of the API are:

* serves a Zarr store API from the root of the dataset
* provides Zarr metadata keys (\ ``.zmetadata``\ ) as json strings.
* provides access to data keys (e.g. ``var/0.0.0``\ ) as binary strings.

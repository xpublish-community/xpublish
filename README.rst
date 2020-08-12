Xpublish
========

Publish Xarray Datasets via a REST API.

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

**Serverside: Publish a Xarray Dataset through a rest API**

.. code-block:: python

   ds.rest.serve(host="0.0.0.0", port=9000)


**Client-side: Connect to a published dataset**

The published dataset can be accessed from various kinds of client applications.
Here is an example of directly accessing the data from within Python:

.. code-block:: python

   import xarray as xr
   import zarr
   from fsspec.implementations.http import HTTPFileSystem

   fs = HTTPFileSystem()
   http_map = fs.get_mapper('http://0.0.0.0:9000')

   # open as a zarr group
   zg = zarr.open_consolidated(http_map, mode='r')

   # or open as another Xarray Dataset
   ds = xr.open_zarr(http_map, consolidated=True)


Why?
^^^^

Xpublish lets you serve/share/publish Xarray Datasets via a web application.

The data and/or metadata in the Xarray Datasets can be exposed in various forms
through pluggable REST API endpoints. Efficient, on-demand delivery of large
datasets may be enabled with Dask on the server-side.

We are exploring applications of Xpublish that include:

* publish on-demand or derived data products
* turning xarray objects into streaming services (e.g. OPeNDAP)

How?
^^^^

Under the hood, Xpublish is using a web app (FastAPI) that is exposing a
REST-like API with builtin and/or user-defined endpoints.

For example, Xpublish provides by default a minimal Zarr compatible REST-like
API with the following endpoints:

* ``.zmetadata``: returns Zarr-formatted metadata keys as json strings.
* ``var/0.0.0``: returns a variable data chunk as a binary string.

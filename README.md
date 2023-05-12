# Xpublish

Publish Xarray Datasets to the web

<!-- badges-start -->

[![PyPI](https://img.shields.io/pypi/v/xpublish)](https://pypi.org/project/xpublish/)
[![Conda](https://img.shields.io/conda/v/conda-forge/xpublish)](https://anaconda.org/conda-forge/xpublish)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/xpublish)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/xpublish-community/xpublish/main)

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/xpublish-community/xpublish/main.yaml?logo=github)](https://github.com/xpublish-community/xpublish/actions/workflows/main.yaml)
[![Documentation Status](https://readthedocs.org/projects/xpublish/badge/?version=latest)](https://xpublish.readthedocs.io/en/latest/?badge=latest)
[![](https://codecov.io/gh/xpublish-community/xpublish/branch/main/graph/badge.svg)](https://codecov.io/gh/xpublish-community/xpublish)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/xpublish-community/xpublish/main.svg)](https://results.pre-commit.ci/latest/github/xpublish-community/xpublish/main)

<!-- badges-end -->

## A quick example

**Serverside: Publish a Xarray Dataset through a rest API**

<!-- server-example-start -->

```python
ds.rest.serve(host="0.0.0.0", port=9000)
```

<!-- server-example-end -->

**Client-side: Connect to a published dataset**

<!-- client-example-start -->

The published datasets can be accessed from various kinds of client applications, e.g., from within Python using Zarr and fsspec.

```python
import xarray as xr
import zarr
from fsspec.implementations.http import HTTPFileSystem

fs = HTTPFileSystem()
http_map = fs.get_mapper("http://0.0.0.0:9000/zarr/")

# open as a zarr group
zg = zarr.open_consolidated(http_map, mode="r")

# or open as another Xarray Dataset
ds = xr.open_zarr(http_map, consolidated=True)
```

Or to explore other access methods, open [http://0.0.0.0:9000/docs](http://0.0.0.0:9000/docs) in a browser.

<!-- client-example-end -->

## Why?

Xpublish lets you serve/share/publish Xarray Datasets via a web application.

The data and/or metadata in the Xarray Datasets can be exposed in various forms through [pluggable REST API endpoints](https://xpublish.readthedocs.io/en/latest/user-guide/plugins.html).
Efficient, on-demand delivery of large datasets may be enabled with Dask on the server-side.

Xpublish's [plugin ecosystem](https://xpublish.readthedocs.io/en/latest/ecosystem/index.html#plugins) has capabilities including:

- publish on-demand or derived data products
- turning xarray objects into streaming services (e.g. OPeNDAP)

## How?

Under the hood, Xpublish is using a web app (FastAPI) that is exposing a
REST-like API with builtin and/or user-defined endpoints.

For example, Xpublish provides by default a minimal Zarr compatible REST-like API with the following endpoints:

- `zarr/.zmetadata`: returns Zarr-formatted metadata keys as json strings.
- `zarr/var/0.0.0`: returns a variable data chunk as a binary string.

Futher endpoints can be added by installing or writing plugins.

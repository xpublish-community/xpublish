[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/jhamman/xpublish/CI?logo=github)](https://github.com/jhamman/xpublish/actions?query=workflow%3ACI)
[![Documentation Status](https://readthedocs.org/projects/xpublish/badge/?version=latest)](https://xpublish.readthedocs.io/en/latest/?badge=latest)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jhamman/xpublish/master)

# xpublish

Publish Xarray Datasets via a Zarr compatible REST API

**Server side: Publish a xarray dataset as a rest API**

```python
ds.rest.serve(host="0.0.0.0", port=9000)
```

**Client side: Connect to a published dataset**

```python

import xarray as xr
import zarr
from fsspec.implementations.http import HTTPFileSystem

fs = HTTPFileSystem()
http_map = fs.get_mapper('http://0.0.0.0:9000')

# open as a zarr group
zg = zarr.open_consolidated(http_map, mode='r')

# open as another xarray dataset
xr.open_zarr(http_map, consolidated=True)
```

### Why?

xpublish lets you serve/share/publish xarray datasets via a web application.
The data in the xarray datasets (on the server side) can be backed by dask to facilitate on-demand computation via a simple REST API.
We are exploring applications of xpublish that include:

- publish on-demand derived data products
- turning xarray objects into streaming services (e.g. OPENDAP)

### How?

Under the hood, xpublish is using a web app (FastAPI) that is exposing a minimal Zarr compatible REST-like API.
Key attributes of the API are:

- serves a Zarr store API from the root of the dataset
- provides Zarr metadata keys (`.zmetadata`) as json strings.
- provides access to data keys (e.g. `var/0.0.0`) as binary strings.

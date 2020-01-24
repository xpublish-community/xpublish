# xpublish

Publish Xarray Datasets via a Zarr compatible REST API

**Publish a xarray dataset as a rest API**
```python
ds.rest.serve()
```

**Connect to a published dataset**
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

Under the hood, xpublish is using a web app (Flask) that is exposing a minimal Zarr compatible REST-like API.
Key attributes of the API are:

- serves a Zarr store API from the root of the dataset
- provides Zarr metadata keys (`.zmetadata`, `.zgroup`, '.zattrs`) as json strings.
- provides access to data keys (e.g. `var/0.0.0`) as binary strings. 


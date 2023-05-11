# Introduction

If you've read through [Why Xpublish](../why-xpublish.md) you'll know that Xpublish is a foundational building block for data servers. The real trick behind Xpublish is that it builds upon the Xarray datasets that the Python data community is used too.

To introduce new users to Xpublish, quickly serve a single dataset, and to allow for quick development, Xpublish includes an [Xarray accessor](https://docs.xarray.dev/en/stable/internals/extending-xarray.html).

## Server-Side

To begin, import Xpublish and open an Xarray {class}`~xarray.Dataset`:

```python
import xarray as xr
import xpublish

ds = xr.tutorial.open_dataset(
    "air_temperature",
    chunks=dict(lat=5, lon=5),
)
```

To publish the dataset, use the
{class}`~xpublish.SingleDatasetRest` class:

```python
rest = xpublish.SingleDatasetRest(ds)
```

Alternatively, you might want to use the {attr}`xarray.Dataset.rest` accessor
for more convenience:

```python
ds.rest
```

Optional customization of the underlying [FastAPI application](https://fastapi.tiangolo.com) or the server-side [cache](https://github.com/dask/cachey) is possible, e.g.,

```python
ds.rest(
    app_kws=dict(
        title="My Dataset",
        description="Dataset Description",
        openapi_url="/dataset.JSON",
    ),
    cache_kws=dict(available_bytes=1e9),
)
```

Serving the dataset then requires calling the
{meth}`~xpublish.Rest.serve` method on the {class}`~xpublish.Rest` instance or
the {attr}`xarray.Dataset.rest` accessor:

```python
rest.serve()

# or

ds.rest.serve()
```

{meth}`~xpublish.Rest.serve` passes any keyword arguments on to
{func}`uvicorn.run` (see [Uvicorn docs]).

### Default API routes

By default, the FastAPI application created with Xpublish provides the following
endpoints to get some information about the published dataset:

- `/`: returns xarray's HTML repr.
- `/keys`: returns a list of variable keys, i.e., those returned by {attr}`xarray.Dataset.variables`.
- `/info`: returns a JSON dictionary summary of a Dataset variables and attributes, similar to {meth}`xarray.Dataset.info`.
- `/dict`: returns a JSON dictionary of the full dataset.
- `/versions`: returns JSON dictionary of the versions of Python, Xarray and related libraries on the server side, similar to {func}`xarray.show_versions`.

The application also provides data access through a [Zarr] compatible API with the
following endpoints:

- `/zarr/.zmetadata`: returns a JSON dictionary representing the consolidated Zarr metadata.
- `/zarr/{var}/{key}`: returns a single chunk of an array.

### API Docs

Thanks to FastAPI and [Swagger UI], automatically generated
interactive documentation is available at the `/docs` URL.

This path can be overridden by setting the `docs_url` key in the `app_kws`
dictionary argument when initializing the rest accessor.

## Client-Side

By default, datasets served by Xpublish can be opened by any Zarr client
that implements an HTTPStore. In Python, this can be done with `fsspec`:

```python
import zarr
from fsspec.implementations.http import HTTPFileSystem

fs = HTTPFileSystem()

# The URL 'http://0.0.0.0:9000/zarr/' here serves one dataset
http_map = fs.get_mapper("http://0.0.0.0:9000/zarr/")

# open as a zarr group
zg = zarr.open_consolidated(http_map, mode="r")

# or open as another Xarray Dataset
ds = xr.open_zarr(http_map, consolidated=True)
```

Xpublish's endpoints can also be queried programmatically. For example:

```python
import requests

response = requests.get("http://0.0.0.0:9000/info").json()
```

[swagger ui]: https://github.com/swagger-api/swagger-ui
[uvicorn docs]: https://www.uvicorn.org/deployment/#running-programmatically
[zarr]: https://zarr.readthedocs.io/en/stable/

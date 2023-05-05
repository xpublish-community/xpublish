# Serving multiple datasets

Xpublish also lets you serve multiple datasets via one FastAPI application. You
provide a mapping (dictionary) when creating a
{class}`~xpublish.Rest` instance, e.g.,

```python
ds = xr.tutorial.open_dataset("air_temperature")
ds2 = xr.tutorial.open_dataset("rasm")

rest_collection = xpublish.Rest({"air_temperature": ds, "rasm": ds2})

rest_collection.serve()
```

When multiple datasets are given, all dataset-specific API endpoint URLs have
the `/datasets/{dataset_id}` prefix. For example:

- `/datasets/rasm/info` returns information about the `rasm` dataset
- `/datasets/invalid_dataset_id/info` returns a 404 HTTP error

The application also has one more API endpoint:

- `/datasets`: returns the list of the ids (keys) of all published datasets

Note that custom routes work for multiple datasets as well as for a single
dataset. No code change is required. Taking the example previously,

```python
rest_collection = xpublish.Rest(
    {"air_temperature": ds, "rasm": ds2}, routers=[myrouter]
)

rest_collection.serve()
```

The following URLs should return expected results:

- `/datasets/air_temperature/air/mean`
- `/datasets/rasm/Tair/mean`

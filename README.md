# Xpublish

Publish Xarray Datasets and DataTrees to the web

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

**Serverside: Publish an Xarray Dataset or DataTree through a REST API**

<!-- server-example-start -->

```python
ds.rest.serve(host="0.0.0.0", port=9000)
# or, for a hierarchical DataTree, the API is identical:
dt.rest.serve(host="0.0.0.0", port=9000)
```

<!-- server-example-end -->

**Client-side: Connect to a published dataset**

<!-- client-example-start -->

The published datasets can be accessed from various kinds of client applications, including any HTTP client. To explore the available endpoints, open [http://0.0.0.0:9000/docs](http://0.0.0.0:9000/docs) in a browser.

<!-- client-example-end -->

## Why?

Xpublish lets you serve/share/publish Xarray Datasets and DataTrees via a web application.

The data and/or metadata can be exposed in various forms through [pluggable REST API endpoints](https://xpublish.readthedocs.io/en/latest/user-guide/plugins.html). Hierarchical data is supported natively — bare Datasets are wrapped in a single-node DataTree internally so the same routes, accessors, and plugins work whether you're serving a flat dataset or a deeply nested tree.
Efficient, on-demand delivery of large datasets may be enabled with Dask on the server-side.

Xpublish's [plugin ecosystem](https://xpublish.readthedocs.io/en/latest/ecosystem/index.html#plugins) has capabilities including:

- publish on-demand or derived data products
- turning xarray objects into streaming services (e.g. OPeNDAP)
- Zarr-compatible access via [xpublish-zarr](https://github.com/xpublish-community/xpublish-zarr)

## How?

Under the hood, Xpublish is using a web app (FastAPI) that is exposing a
REST-like API with builtin and/or user-defined endpoints. Additional
endpoints can be added by installing or writing plugins.

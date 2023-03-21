import cachey
import xarray as xr
from fastapi import FastAPI

from .rest import SingleDatasetRest


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """REST API Accessor for serving one dataset in its
    dedicated FastAPI application.

    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj
        self._rest = None

        self._initialized = False

    def _get_rest_obj(self):
        if self._rest is None:
            self._rest = SingleDatasetRest(self._obj)

        return self._rest

    def __call__(self, **kwargs):
        """Initialize this accessor by setting optional configuration values.

        Parameters
        ----------
        **kwargs
            Arguments passed to :func:`xpublish.SingleDatasetRest.__init__`.

        Notes
        -----
        This method can only be invoked once.

        """
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        self._rest = SingleDatasetRest(self._obj, **kwargs)

        return self

    @property
    def cache(self) -> cachey.Cache:
        """Returns the :class:`cachey.Cache` instance used by the FastAPI application."""

        return self._get_rest_obj().cache

    @property
    def app(self) -> FastAPI:
        """Returns the :class:`fastapi.FastAPI` application instance."""

        return self._get_rest_obj().app

    def serve(self, **kwargs):
        """Serve this FastAPI application via :func:`uvicorn.run`.

        Parameters
        ----------
        **kwargs :
            Arguments passed to :func:`xpublish.SingleDatasetRest.serve`.

        Notes
        -----
        This method is blocking and does not return.

        """
        self._get_rest_obj().serve(**kwargs)

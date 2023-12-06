import cachey
import xarray as xr
from fastapi import FastAPI

from .rest import SingleDatasetRest


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """REST API Accessor for serving one dataset via a dedicated FastAPI app."""

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

        NOTE: This method can only be invoked once.

        Args:
            **kwargs: Arguments passed to :func:`xpublish.SingleDatasetRest.__init__`.

        Returns:
            The initialized accessor.
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

        NOTE: This method is blocking and does not return.

        Args:
            **kwargs: Arguments passed to :func:`xpublish.SingleDatasetRest.serve`.
        """
        self._get_rest_obj().serve(**kwargs)

.. currentmodule:: xpublish

#############
API reference
#############

Dataset.rest (xarray accessor)
==============================

This accessor extends :py:class:`xarray.Dataset` with all the methods and
properties listed below. Proper use of this accessor should be like:

.. code-block:: python

   >>> import xarray as xr         # first import xarray
   >>> import xpublish             # import xpublish (the 'rest' accessor is registered for datasets)
   >>> ds = xr.Dataset()           # create or load an xarray Dataset
   >>> ds.rest(...)                # call the 'rest' accessor
   >>> ds.rest.<meth_or_prop>      # access to the methods and properties listed below

.. currentmodule:: xarray

**Calling the accessor**

.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_callable.rst

   Dataset.rest

**Properties**

.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_attribute.rst

   Dataset.rest.app
   Dataset.rest.cache

**Methods**

.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_method.rst

   Dataset.rest.serve

FastAPI dependencies
====================

The functions below are defined in module ``xpublish.dependencies`` and can
be used as FastAPI dependencies when creating custom API endpoints.

.. currentmodule:: xpublish.dependencies

.. autosummary::
   :toctree: generated/

   get_dataset
   get_cache
   get_zvariables
   get_zmetadata

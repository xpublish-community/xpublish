.. currentmodule:: xpublish

#############
API reference
#############

Top-level Rest class
====================

The :class:`~xpublish.Rest` class can be used for publishing a
:class:`xarray.Dataset` object or a collection of Dataset objects.

.. autosummary::
   :toctree: generated/

   Rest
   Rest.app
   Rest.cache
   Rest.serve

Dataset.rest (xarray accessor)
==============================

This accessor extends :py:class:`xarray.Dataset` with the same interface than
:class:`~xpublish.Rest`. It is a convenient method for publishing one single
dataset. Proper use of this accessor should be like:

.. code-block:: python

   >>> import xarray as xr         # first import xarray
   >>> import xpublish             # import xpublish (the dataset 'rest' accessor is registered)
   >>> ds = xr.Dataset()           # create or load an xarray Dataset
   >>> ds.rest(...)                # call the 'rest' accessor on the dataset
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

   get_dataset_ids
   get_dataset
   get_cache
   get_zvariables
   get_zmetadata

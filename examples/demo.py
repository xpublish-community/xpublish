import xarray as xr
from requests import HTTPError

from xpublish import Plugin, Rest, hookimpl


class TutorialDataset(Plugin):
    """Demonstrates how to create a plugin to load a dataset for demo purposes.
    This uses the default xarray tutorial datasets.
    """

    name: str = 'xarray-tutorial-datasets'

    @hookimpl
    def get_datasets(self):
        """Returns a list of available datasets"""
        return list(xr.tutorial.file_formats)

    @hookimpl
    def get_dataset(self, dataset_id: str):
        """Returns a dataset specified by dataset_id"""
        try:
            ds = xr.tutorial.open_dataset(dataset_id)
            if ds.cf.coords['longitude'].dims[0] == 'longitude':
                ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180)).sortby(
                    'longitude'
                )
                # TODO: Yeah this should not be assumed... but for regular grids we will viz with rioxarray so for now we will assume
                ds = ds.rio.write_crs(4326)
            return ds
        except HTTPError:
            return None


rest = Rest({})
rest.register_plugin(TutorialDataset())

### For this tutorial, you can uncomment the following lines to activate the other plugins:

from lme import LmeSubsetPlugin
from mean import MeanPlugin

rest.register_plugin(MeanPlugin())
rest.register_plugin(LmeSubsetPlugin())

rest.serve()

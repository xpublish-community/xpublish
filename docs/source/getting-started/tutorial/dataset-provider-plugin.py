import xarray as xr
from requests import HTTPError

from xpublish import Plugin, Rest, hookimpl


class TutorialDataset(Plugin):
    name = 'xarray-tutorial-dataset'

    @hookimpl
    def get_datasets(self):
        return list(xr.tutorial.file_formats)

    @hookimpl
    def get_dataset(self, dataset_id: str):
        try:
            return xr.tutorial.open_dataset(dataset_id)
        except HTTPError:
            return None


rest = Rest({})
rest.register_plugin(TutorialDataset())
rest.serve()

import xarray as xr
from requests import HTTPError

from xpublish import Plugin, Rest, hookimpl


class TutorialDataset(Plugin):
    name: str = 'xarray-tutorial-dataset'

    @hookimpl
    def get_datasets(self):
        return list(xr.tutorial.file_formats)

    @hookimpl
    def get_datatree(self, dataset_id: str, group: str):
        # The xarray tutorial datasets are flat, so we only serve the root.
        # Note: ``group`` must be a positional parameter (no default) — pluggy
        # will not forward arguments that have defaults to the hookimpl.
        if group:
            return None
        try:
            ds = xr.tutorial.open_dataset(dataset_id)
        except HTTPError:
            return None
        return xr.DataTree(dataset=ds)


rest = Rest({})
rest.register_plugin(TutorialDataset())
rest.serve()

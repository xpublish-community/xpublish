from typing import Sequence

from fastapi import APIRouter
from xpublish import Plugin, Dependencies, hookimpl

regions = {
    "GB": {"bbox": [-69.873, -65.918, 40.280, 42.204], "name": "Georges Bank"},
    "GOM": {"bbox": [-70.975, -65.375, 40.375, 45.125], "name": "Gulf Of Maine"},
    "MAB": {
        "bbox": [-77.036, -70.005, 35.389, 41.640],
        "name": "MidAtlantic Bight",
    },
    "NESHELF": {
        "bbox": [-77.45, -66.35, 34.50, 44.50],
        "name": "North East Shelf",
    },
    "SS": {"bbox": [-66.775, -65.566, 41.689, 45.011], "name": "Scotian Shelf"},
    "EC": {"bbox": [-81.75, -65.375, 25.000, 45.125], "name": "East Coast"},
    "NEC": {"bbox": [-81.45, -63.30, 28.70, 44.80], "name": "Northeast Coast"},
}

DEFAULT_TAGS = ['lme', 'large marine ecosystem', 'subset']


class LmeSubsetPlugin(Plugin):
    name: str = "lme-subset-plugin"

    app_router_prefix: str = "/lme"
    app_router_tags: Sequence[str] = DEFAULT_TAGS

    dataset_router_prefix: str = '/lme'
    dataset_router_tags: Sequence[str] = DEFAULT_TAGS

    @hookimpl
    def app_router(self):
        router = APIRouter(prefix=self.app_router_prefix, tags=list(self.app_router_tags))

        @router.get("/")
        def get_lme_regions():
            return {key: value["name"] for key, value in regions.items()}

        return router
    
    #    @router.get("/{lme_name}")
    #    def get_lme_regions(lme_name: str):
    #        return regions[lme_name].bbox

    #    return router

    

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        def get_region_dataset(dataset_id: str, region_id: str):
            region = regions[region_id]
            bbox = region['bbox']

            # lat_slice = slice(bbox[2], bbox[3])
            lat_slice = slice(bbox[3], bbox[2])  # air_temperature lats are descending
            # lon_slice = slice(bbox[0], bbox[1])

            # print(lat_slice, lon_slice)

            dataset = deps.dataset(dataset_id)

            sliced = dataset.cf.sel(latitude=lat_slice)

            return sliced
        
        region_deps = Dependencies(
            dataset_ids=deps.dataset_ids,
            dataset=get_region_dataset,
            cache=deps.cache,
            plugins=deps.plugins,
            plugin_manager=deps.plugin_manager,
        )

        all_plugins = list(deps.plugin_manager().get_plugins())
        this_plugin = [p for p in all_plugins if p.name == self.name]

        for new_router in deps.plugin_manager().subset_hook_caller('dataset_router', 
                        remove_plugins=this_plugin)(deps=region_deps):
            router.include_router(new_router, prefix="/{region_id}")

        return router

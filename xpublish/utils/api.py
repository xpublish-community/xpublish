from fastapi import APIRouter


def normalize_app_routers(routers):

    new_routers = []

    for rt in routers:
        if isinstance(rt, APIRouter):
            new_routers.append((rt, {}))
        elif isinstance(rt, tuple) and isinstance(rt[0], APIRouter) and len(rt) == 2:
            new_routers.append(rt)
        else:
            raise ValueError(
                "Invalid format for routers item, please provide either an APIRouter "
                "instance or a (APIRouter, {...}) tuple."
            )

    return new_routers

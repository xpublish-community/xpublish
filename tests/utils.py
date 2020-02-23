from starlette.testclient import TestClient


class TestMapper(TestClient):
    """
    A simple subclass to support getitem syntax on Starlette TestClient Objects
    """

    def __getitem__(self, key):
        response = self.get(key)
        if response.status_code != 200:
            raise KeyError("{} not found. status_code = {}".format(key, response.status_code))
        return response.content

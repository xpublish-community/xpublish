import time


class CostTimer:
    """Context manager to measure wall time"""

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        end = time.perf_counter()
        self.time = end - self._start

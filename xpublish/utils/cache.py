import time


class CostTimer:
    """Context manager to measure wall time."""

    def __enter__(self):
        """Start the timer."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        """Stop the timer and return elapsed time."""
        end = time.perf_counter()
        self.time = end - self._start

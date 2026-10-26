"""Separate exploration: a four-minute gradual 20, 50, 100, 200-user ramp."""
from locust import LoadTestShape
from search import SearchUser


class SearchRamp(LoadTestShape):
    stages = ((60, 20), (120, 50), (180, 100), (240, 200))

    def tick(self):
        elapsed = self.get_run_time()
        for end, users in self.stages:
            if elapsed < end:
                return users, 20
        return None

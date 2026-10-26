"""Separate exploration: 20 users for 60s, 100 for 180s, then 20 for 60s."""
from locust import LoadTestShape
from search import SearchUser


class SearchSpike(LoadTestShape):
    stages = ((60, 20), (240, 100), (300, 20))

    def tick(self):
        elapsed = self.get_run_time()
        for end, users in self.stages:
            if elapsed < end:
                return users, 100
        return None

from locust import HttpUser, task, between

class URLShortenerUser(HttpUser):
    # Simulated users will wait between 1 and 3 seconds between actions
    wait_time = between(1, 3)

    @task(1)
    def test_health_check(self):
        """Simulates a user hitting the health check endpoint."""
        self.client.get("/health")

    @task(2)
    def test_url_redirect(self):
        """
        Simulates a user clicking your shortened link.
        We use catch_response=True because a 302 redirect is an expected success,
        but by default, Locust might try to follow it or log it weirdly.
        """
        with self.client.get("/api/v1/r/enqLbP", allow_redirects=False, catch_response=True) as response:
            if response.status_code == 302:
                response.success()
            else:
                response.failure(f"Expected 302, got {response.status_code}")
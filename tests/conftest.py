import pytest


@pytest.fixture(autouse=True)
def _no_http_requests(monkeypatch):
    def urlopen_mock(self, method, url, *_args, **_kwargs):
        raise RuntimeError(
            f"The test was about to {method} {self.scheme}://{self.host}{url}"
        )

    monkeypatch.setattr(
        "urllib3.connectionpool.HTTPConnectionPool.urlopen", urlopen_mock
    )

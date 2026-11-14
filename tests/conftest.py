import socket

import pytest

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@pytest.fixture(autouse=True)
def no_internet(request, monkeypatch):
    """Fail any test, other than the live checks, that tries to reach the internet."""
    if request.node.get_closest_marker("live"):
        yield
        return

    blocked: list[str] = []
    getaddrinfo = socket.getaddrinfo

    def local_only(host, *args, **kwargs):
        if host not in LOCAL_HOSTS:
            blocked.append(str(host))
            raise OSError(f"Blocked by tests/conftest.py: lookup of {host}")
        return getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_only)
    yield
    assert not blocked, f"The test tried to reach {sorted(set(blocked))}"

"""Tests for EDGAR fetcher retry behavior."""
import copy

import pytest
import requests

from dri.edgar import EDGARFetcher


class FakeResponse:
    """Minimal fake response for requests.get."""

    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def _make_fetcher(test_config):
    config = copy.deepcopy(test_config)
    config["edgar"]["retry_attempts"] = 2
    config["edgar"]["retry_delay_sec"] = 1
    return EDGARFetcher(config)


def test_make_request_retries_on_429(monkeypatch, test_config):
    fetcher = _make_fetcher(test_config)
    fetcher._rate_limit_sleep = lambda: None

    responses = [
        FakeResponse(429, headers={"Retry-After": "5"}),
        FakeResponse(200),
    ]
    call_count = {"count": 0}
    sleeps = []

    def fake_get(url, headers=None, timeout=30):
        call_count["count"] += 1
        return responses.pop(0)

    monkeypatch.setattr("dri.edgar.requests.get", fake_get)
    monkeypatch.setattr("dri.edgar.time.sleep", lambda seconds: sleeps.append(seconds))

    response = fetcher._make_request("https://example.com")

    assert response.status_code == 200
    assert call_count["count"] == 2
    assert sleeps and sleeps[0] == pytest.approx(5.0)


def test_make_request_retries_on_408(monkeypatch, test_config):
    fetcher = _make_fetcher(test_config)
    fetcher._rate_limit_sleep = lambda: None

    responses = [FakeResponse(408), FakeResponse(200)]
    call_count = {"count": 0}
    sleeps = []

    def fake_get(url, headers=None, timeout=30):
        call_count["count"] += 1
        return responses.pop(0)

    monkeypatch.setattr("dri.edgar.requests.get", fake_get)
    monkeypatch.setattr("dri.edgar.time.sleep", lambda seconds: sleeps.append(seconds))

    response = fetcher._make_request("https://example.com")

    assert response.status_code == 200
    assert call_count["count"] == 2
    assert sleeps and sleeps[0] == pytest.approx(1.0)


def test_make_request_does_not_retry_on_400(monkeypatch, test_config):
    fetcher = _make_fetcher(test_config)
    fetcher._rate_limit_sleep = lambda: None

    call_count = {"count": 0}

    def fake_get(url, headers=None, timeout=30):
        call_count["count"] += 1
        return FakeResponse(400)

    monkeypatch.setattr("dri.edgar.requests.get", fake_get)

    with pytest.raises(requests.HTTPError):
        fetcher._make_request("https://example.com")

    assert call_count["count"] == 1

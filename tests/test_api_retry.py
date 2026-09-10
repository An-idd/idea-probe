from __future__ import annotations

import httpx
import pytest

import api_retry


def test_exception_retries_share_one_attempt_budget():
    calls = []
    waits = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = api_retry.retry_call(flaky, attempts=3, sleep=waits.append)

    assert result == "ok"
    assert len(calls) == 3
    assert waits == [1.0, 2.0]


def test_exhausted_exception_keeps_every_failure():
    with pytest.raises(api_retry.RetryError) as exc_info:
        api_retry.retry_call(
            lambda: (_ for _ in ()).throw(TimeoutError("temporary")),
            attempts=2,
            sleep=lambda _delay: None,
            operation_name="test endpoint",
        )

    assert len(exc_info.value.failures) == 2
    assert "第 1 次" in str(exc_info.value)
    assert "第 2 次" in str(exc_info.value)


def test_http_retries_only_transient_statuses():
    responses = iter([
        httpx.Response(503),
        httpx.Response(429, headers={"retry-after": "7"}),
        httpx.Response(200),
    ])
    waits = []

    response = api_retry.retry_http(
        lambda: next(responses), attempts=3, sleep=waits.append)

    assert response.status_code == 200
    assert waits == [1.0, 7.0]


def test_http_does_not_retry_authentication_errors():
    calls = []

    response = api_retry.retry_http(
        lambda: calls.append(1) or httpx.Response(401),
        attempts=3,
        sleep=lambda _delay: pytest.fail("401 must not sleep"),
    )

    assert response.status_code == 401
    assert len(calls) == 1


def test_http_does_not_retry_non_transport_exceptions():
    calls = []

    with pytest.raises(ValueError, match="bad request setup"):
        api_retry.retry_http(
            lambda: calls.append(1) or (_ for _ in ()).throw(
                ValueError("bad request setup")),
            attempts=3,
            sleep=lambda _delay: pytest.fail("configuration errors must not sleep"),
        )

    assert len(calls) == 1

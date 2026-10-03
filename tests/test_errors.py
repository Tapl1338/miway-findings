import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request
from starlette.responses import Response

from app import config, errors


def test_dispatch_normal_request():
    """A healthy call_next result passes through untouched."""
    mock_call_next = AsyncMock()
    mock_request = MagicMock(spec=Request)
    mock_response = Response("OK")
    mock_call_next.return_value = mock_response

    middleware = errors.UnhandledErrorMiddleware(lambda x: x)
    result = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    assert result.status_code == 200
    mock_call_next.assert_called_once_with(mock_request)


def test_dispatch_exception_becomes_sanitized_500():
    """Unhandled exceptions: sanitized body + X-Error-Id, no str(exc)."""
    mock_call_next = AsyncMock()
    mock_request = MagicMock(spec=Request)
    mock_request.method = "GET"
    mock_request.url.path = "/test"
    mock_call_next.side_effect = RuntimeError("secret /etc/passwd detail")

    middleware = errors.UnhandledErrorMiddleware(lambda x: x)
    result = asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    assert result.status_code == 500
    assert result.body == b'{"detail":"Internal server error (see server logs)"}'
    error_id = result.headers["X-Error-Id"]
    assert len(error_id) == 12
    assert all(c in "0123456789abcdef" for c in error_id)


class TestInternalError:
    def test_internal_error_logs_and_raises(self):
        mock_logger = MagicMock()
        mock_exc = ValueError("test error")

        with pytest.raises(HTTPException) as exc_info:
            errors.internal_error(mock_logger, "test message", mock_exc)

        mock_logger.exception.assert_called_once()
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "test message (see server logs)"
        assert exc_info.value.__cause__ is mock_exc


class TestResolvePeriod:
    def test_resolve_period_with_valid_period(self):
        result = errors.resolve_period("am_rush")
        assert result == "am_rush"

    def test_resolve_period_with_none_defaults(self):
        result = errors.resolve_period(None)
        assert result == config.DEFAULT_TIME_PERIOD

    def test_resolve_period_with_unknown_period(self):
        with pytest.raises(HTTPException) as exc_info:
            errors.resolve_period("invalid_period")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "Unknown period: invalid_period"


class TestPeriodWindow:
    def test_period_window_with_valid_period(self):
        # TIME_PERIODS values are (label, start_min, end_min); the window
        # helper returns (name, start, end) without the label.
        result = errors.period_window("am_rush")
        expected = config.TIME_PERIODS["am_rush"]
        assert result == ("am_rush", expected[1], expected[2])

    def test_period_window_with_none_defaults(self):
        result = errors.period_window(None)
        expected = config.TIME_PERIODS[config.DEFAULT_TIME_PERIOD]
        assert result == (config.DEFAULT_TIME_PERIOD, expected[1], expected[2])

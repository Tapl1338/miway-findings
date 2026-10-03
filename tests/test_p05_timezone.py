"""P0.5 regression tests: timezone-aware Toronto/UTC handling in app/."""

from app import config


class TestTorontoToday:
    """P0.5: 'today' anchored to the Toronto service day, not the host clock."""

    def test_returns_date_type(self):
        from datetime import date

        t = config.toronto_today()
        assert isinstance(t, date)

    def test_matches_toronto_zone_date(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        assert (
            config.toronto_today() == datetime.now(ZoneInfo("America/Toronto")).date()
        )

    def test_differs_from_host_utc_early_morning(self):
        # The reason the helper exists: on a UTC host between 00:00 and
        # 04:59 Toronto time, date.today() (UTC) returns YESTERDAY while
        # toronto_today() returns today. Pin the mechanism: the helper must
        # read the clock IN the Toronto zone, not call date.today().
        import ast
        import inspect

        src = inspect.getsource(config.toronto_today)
        assert "_TORONTO_TZ" in src
        # Strip the docstring before scanning: the doc mentions date.today()
        # as the anti-pattern; only real code calls must be banned.
        tree = ast.parse(src)
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not any("date.today" in c for c in calls), calls
        assert any("now" in c for c in calls), calls

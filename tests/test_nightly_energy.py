"""Execute the nightly sync without importing Home Assistant or contacting a device."""

import ast
from datetime import datetime, timedelta
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


def run_inline(function):
    """Drive immediately completing mocks without a Windows event-loop socket."""
    def run(self):
        coroutine = function(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        self.fail("Test unexpectedly suspended on external I/O")
    return run


class NightlyEnergyTests(unittest.TestCase):
    @run_inline
    async def test_finalized_values_refresh_without_touching_recorder_on_restart(self):
        path = Path(__file__).resolve().parents[1] / "custom_components/kronoterm/coordinator.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == "_sync_previous_day_statistics")
        now = datetime(2026, 10, 18, 0, 5)
        namespace = {
            "dt_util": SimpleNamespace(now=lambda: now),
            "timedelta": timedelta,
            "ENERGY_DATA_KEYS": ("heating", "dhw", "circulation", "additional"),
            "_LOGGER": logging.getLogger(__name__),
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
        coordinator = SimpleNamespace(
            _last_stats_sync_date=None,
            _fetch_consumption=AsyncMock(return_value={"trend_consumption": {
                "heating": [9.0, 10.0], "dhw": [2.0], "circulation": [0.7],
            }}),
            _import_energy_statistics_for_date=AsyncMock(),
            hass=Mock(),
        )
        sync = namespace["_sync_previous_day_statistics"]
        await sync(coordinator)
        self.assertEqual(coordinator.previous_day_energy["combined"], 12.7)
        self.assertEqual(coordinator.previous_day_energy_date, now.date() - timedelta(days=1))
        await sync(coordinator)
        coordinator._fetch_consumption.assert_awaited_once_with(day_offset=-1)
        coordinator._last_stats_sync_date = None  # A restart clears the in-memory guard.
        await sync(coordinator)
        self.assertEqual(coordinator._fetch_consumption.await_count, 2)
        coordinator._import_energy_statistics_for_date.assert_not_awaited()
        self.assertEqual(coordinator.hass.mock_calls, [])


if __name__ == "__main__":
    unittest.main()

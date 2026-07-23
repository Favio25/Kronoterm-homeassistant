"""Pure helpers for rebuilding Kronoterm daily energy statistics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
import math


ENERGY_VALUE_EPSILON = 1e-9
MAX_HISTORY_DAYS = 3650
EMPTY_HISTORY_STOP_DAYS = 366


def normalize_energy_series(
    trend: Mapping[str, object],
    keys: Iterable[str],
) -> dict[str, list[float]]:
    """Return finite numeric daily series for the requested energy keys."""
    normalized: dict[str, list[float]] = {}
    for key in keys:
        raw_values = trend.get(key, [])
        if not isinstance(raw_values, (list, tuple)):
            normalized[key] = []
            continue

        values: list[float] = []
        for raw_value in raw_values:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = 0.0
            values.append(value if math.isfinite(value) else 0.0)
        normalized[key] = values
    return normalized


def energy_window_length(series_map: Mapping[str, list[float]]) -> int:
    """Return the longest series length in a consumption response."""
    return max((len(values) for values in series_map.values()), default=0)


def energy_window_has_data(series_map: Mapping[str, list[float]]) -> bool:
    """Return whether a response contains any actual energy consumption."""
    return any(
        abs(value) > ENERGY_VALUE_EPSILON
        for values in series_map.values()
        for value in values
    )


def merge_energy_window(
    day_values: dict[date, dict[str, float]],
    window_end: date,
    series_map: Mapping[str, list[float]],
    entity_ids: Mapping[str, str],
    energy_keys: Iterable[str],
) -> tuple[date, date] | None:
    """Merge one oldest-to-newest API window without duplicating days."""
    length = energy_window_length(series_map)
    if length == 0:
        return None

    keys = tuple(energy_keys)
    window_start = window_end - timedelta(days=length - 1)
    for offset in range(length):
        day = window_start + timedelta(days=offset)
        if day in day_values:
            continue

        values_for_day: dict[str, float] = {}
        for key, entity_id in entity_ids.items():
            if key == "combined":
                values_for_day[entity_id] = sum(
                    series_map.get(energy_key, [])[offset]
                    if offset < len(series_map.get(energy_key, []))
                    else 0.0
                    for energy_key in keys
                )
                continue

            values = series_map.get(key, [])
            if offset < len(values):
                values_for_day[entity_id] = values[offset]

        day_values[day] = values_for_day

    return window_start, window_end


def trim_history_to_first_energy(
    day_values: Mapping[date, dict[str, float]],
) -> dict[date, dict[str, float]]:
    """Drop synthetic leading zero days returned before installation."""
    first_energy_day = next(
        (
            day
            for day in sorted(day_values)
            if any(
                abs(value) > ENERGY_VALUE_EPSILON
                for value in day_values[day].values()
            )
        ),
        None,
    )
    if first_energy_day is None:
        return {}

    return {
        day: dict(values)
        for day, values in day_values.items()
        if day >= first_energy_day
    }


def cumulative_energy_rows(
    day_values: Mapping[date, dict[str, float]],
    entity_ids: Iterable[str],
    handover_date: date,
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, float]]:
    """Build monotonic cumulative rows strictly before the live handover."""
    entity_ids = tuple(entity_ids)
    totals = {entity_id: 0.0 for entity_id in entity_ids}
    rows = {entity_id: [] for entity_id in entity_ids}

    for day in sorted(day_values):
        if day >= handover_date:
            continue
        values = day_values[day]
        for entity_id in entity_ids:
            totals[entity_id] += max(0.0, float(values.get(entity_id, 0.0)))
            rows[entity_id].append((day, totals[entity_id]))

    return rows, totals


def infer_previous_live_offset(
    historical_sum: float,
    first_live_sum: float | None,
) -> float:
    """Infer whether a prior import offset is already present on live rows."""
    if (
        first_live_sum is not None
        and first_live_sum >= historical_sum - ENERGY_VALUE_EPSILON
    ):
        return historical_sum
    return 0.0

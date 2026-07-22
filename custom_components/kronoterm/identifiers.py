"""Stable identifiers shared by Kronoterm platforms and migrations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
from typing import Any

from .const import DOMAIN

ENERGY_DATA_KEYS: tuple[str, ...] = (
    "CompHeating",
    "CompTapWater",
    "CPLoops",
    "CPAddSource",
)


def cloud_config_unique_id(username: str, system_type: str) -> str:
    """Return a non-reversible account ID for duplicate-flow prevention."""
    normalized_username = username.strip().casefold()
    account_hash = hashlib.sha256(normalized_username.encode()).hexdigest()[:20]
    return f"cloud:{system_type}:{account_hash}"


def modbus_config_unique_id(
    transport: str,
    endpoint: str,
    port: int | str,
    unit_id: int | str,
) -> str:
    """Return a stable local connection ID for duplicate-flow prevention."""
    return f"modbus:{transport}:{endpoint.strip().casefold()}:{port}:{unit_id}"


def config_unique_id_from_data(data: Mapping[str, Any]) -> str | None:
    """Build the setup-flow unique ID for an existing config entry."""
    if data.get("connection_type", "cloud") == "modbus":
        transport = str(data.get("transport", "tcp"))
        endpoint = (
            data.get("serial_port")
            if transport == "rtu"
            else data.get("host")
        )
        if not endpoint:
            return None
        return modbus_config_unique_id(
            transport,
            str(endpoint),
            0 if transport == "rtu" else data.get("port", 502),
            data.get("unit_id", 20),
        )

    username = data.get("username")
    if not username:
        return None
    return cloud_config_unique_id(
        str(username), str(data.get("system_type", "cloud"))
    )


def daily_energy_unique_id(entry_id: str, data_key: str) -> str:
    """Return an entry-scoped unique ID for a daily energy sensor."""
    return f"{entry_id}_{DOMAIN}_daily_{data_key}"


def combined_energy_unique_id(
    entry_id: str, data_keys: Iterable[str] = ENERGY_DATA_KEYS
) -> str:
    """Return an entry-scoped unique ID for the combined daily sensor."""
    return f"{entry_id}_{DOMAIN}_daily_combined_{'_'.join(data_keys)}"


def calculated_power_unique_id(
    entry_id: str, data_keys: Iterable[str] = ENERGY_DATA_KEYS
) -> str:
    """Return an entry-scoped unique ID for the calculated-power sensor."""
    return f"{entry_id}_{DOMAIN}_calculated_power_{'_'.join(data_keys)}"


def legacy_energy_unique_id_migrations(entry_id: str) -> dict[str, str]:
    """Map pre-1.6.10 global energy IDs to entry-scoped IDs."""
    migrations = {
        f"{DOMAIN}_daily_{key}": daily_energy_unique_id(entry_id, key)
        for key in ENERGY_DATA_KEYS
    }
    joined_keys = "_".join(ENERGY_DATA_KEYS)
    migrations[f"{DOMAIN}_daily_combined_{joined_keys}"] = (
        combined_energy_unique_id(entry_id)
    )
    migrations[f"{DOMAIN}_calculated_power_{joined_keys}"] = (
        calculated_power_unique_id(entry_id)
    )
    return migrations

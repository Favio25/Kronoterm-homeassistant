"""Redacted diagnostics support for Kronoterm config entries."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, INTEGRATION_VERSION

TO_REDACT = {
    "host",
    "password",
    "serial_port",
    "token",
    "username",
}


def _safe_device_info(device_info: dict[str, Any]) -> dict[str, Any]:
    """Make device information JSON-safe without exposing identifiers."""
    return {
        key: value
        for key, value in device_info.items()
        if key not in {"identifiers", "connections"}
    }


def _cloud_page_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Describe Cloud response structure without including response values."""
    summary: dict[str, Any] = {}
    for page, value in data.items():
        if isinstance(value, dict):
            summary[page] = {
                "available": True,
                "fields": sorted(str(key) for key in value),
            }
        else:
            summary[page] = {"available": value is not None}
    return summary


def _modbus_register_snapshot(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a value snapshot keyed by documented register address."""
    main = data.get("main", {}) if isinstance(data, dict) else {}
    registers = main.get("ModbusReg", []) if isinstance(main, dict) else []
    return [
        {
            "address": register.get("address"),
            "name": register.get("name"),
            "value": register.get("value"),
            "unit": register.get("unit"),
        }
        for register in registers
        if isinstance(register, dict)
    ]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for one Kronoterm config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    connection_type = entry.data.get("connection_type", "cloud")
    data = coordinator.data if isinstance(coordinator.data, dict) else {}

    diagnostics: dict[str, Any] = {
        "integration_version": INTEGRATION_VERSION,
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "health": {
            "last_update_success": coordinator.last_update_success,
            "last_successful_update": getattr(
                coordinator, "last_successful_update", None
            ),
            "last_update_duration_ms": getattr(
                coordinator, "last_update_duration_ms", None
            ),
            "last_error_type": getattr(coordinator, "last_update_error", None),
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
        "device": _safe_device_info(
            getattr(coordinator, "shared_device_info", {})
        ),
        "features": {
            name: getattr(coordinator, name, None)
            for name in (
                "loop1_installed",
                "loop2_installed",
                "loop3_installed",
                "loop4_installed",
                "tap_water_installed",
                "reservoir_installed",
                "pool_installed",
                "alt_source_installed",
                "additional_source_installed",
            )
        },
    }

    if connection_type == "modbus":
        diagnostics["connection"] = {
            "type": "modbus",
            "transport": entry.data.get("transport", "tcp"),
            "register_profile": getattr(coordinator, "register_set", "unknown"),
            "unit_id": entry.data.get("unit_id"),
        }
        diagnostics["register_snapshot"] = _modbus_register_snapshot(data)
    else:
        diagnostics["connection"] = {
            "type": "cloud",
            "system_type": entry.data.get("system_type", "cloud"),
            "authentication_mode": getattr(coordinator, "auth_mode", None),
        }
        diagnostics["cloud_pages"] = _cloud_page_summary(data)
        finalized_date = getattr(coordinator, "previous_day_energy_date", None)
        diagnostics["finalized_energy_date"] = (
            finalized_date.isoformat() if finalized_date else None
        )

    return diagnostics

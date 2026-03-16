import logging
from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return

    # Only add for main cloud coordinator (energy consumption comes from cloud)
    system_type = getattr(coordinator, "system_type", "cloud")
    if system_type in ("dhw", "modbus"):
        return

    async_add_entities([KronotermEnergyReimportInfo(coordinator, entry)])


class KronotermEnergyReimportInfo(CoordinatorEntity, TextEntity):
    _attr_has_entity_name = True
    _attr_name = "Energy Reimport Info"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_mode = "text"

    def __init__(self, coordinator: Any, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_energy_reimport_info"
        self._attr_device_info = coordinator.shared_device_info
        self._attr_native_value = (
            "Reimport clears statistics. Hourly (short-term) stats may disappear until HA rebuilds them."
        )

    async def async_set_value(self, value: str) -> None:
        # Read-only informational entity
        return

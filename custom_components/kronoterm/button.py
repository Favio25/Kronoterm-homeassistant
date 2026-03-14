import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
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
    if getattr(coordinator, "system_type", "cloud") == "dhw":
        return

    _LOGGER.info("Adding Reimport Energy Statistics button for entry %s", entry.entry_id)
    async_add_entities([KronotermReimportEnergyButton(coordinator, entry)])


class KronotermReimportEnergyButton(CoordinatorEntity, ButtonEntity):
    """Button to re-import all available energy statistics."""

    _attr_has_entity_name = True
    _attr_translation_key = "reimport_energy_statistics"
    _attr_name = "Reimport Energy Statistics"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Any, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_reimport_energy_statistics"
        self._attr_device_info = coordinator.shared_device_info

    async def async_press(self) -> None:
        _LOGGER.info("Manual re-import of energy statistics triggered")
        if hasattr(self.coordinator, "reimport_all_energy_statistics"):
            await self.coordinator.reimport_all_energy_statistics()
        else:
            _LOGGER.error("Coordinator missing reimport_all_energy_statistics method")

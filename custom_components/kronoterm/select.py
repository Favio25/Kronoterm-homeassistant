import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def extract_modbus_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the list of Modbus registers from the coordinator data."""
    return data.get("main", {}).get("ModbusReg", [])

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kronoterm select entities for different operations."""
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return

    modbus_list = extract_modbus_list(coordinator.data or {})

    # Define the configuration for each select entity.
    entity_configs = [
        {"name": "Loop 1 Operation", "address": 2042, "page": 5},
        {"name": "Loop 2 Operation", "address": 2052, "page": 6},
        {"name": "Sanitary Water Operation", "address": 2026, "page": 9},
    ]

    entities = []
    for config in entity_configs:
        address = config["address"]
        if any(reg.get("address") == address for reg in modbus_list):
            entities.append(
                KronotermModeSelect(
                    entry=entry,
                    name=config["name"],
                    address=address,
                    page=config["page"],
                    coordinator=coordinator,
                )
            )
        else:
            _LOGGER.info(
                "%s register (%s) not found, skipping %s select entity.",
                config["name"].split()[0],
                address,
                config["name"],
            )

    async_add_entities(entities, update_before_add=True)


class KronotermModeSelect(CoordinatorEntity, SelectEntity):
    """
    Select entity for Kronoterm offering three options: OFF, ON, AUTO.
    
    The current mode is determined by a Modbus register value.
    Changing the selection calls coordinator.async_set_loop_mode_by_page.
    """

    _attr_options = ["OFF", "ON", "AUTO"]

    # Mapping for converting register values to select options.
    VALUE_TO_OPTION = {0: "OFF", 1: "ON", 2: "AUTO"}
    OPTION_TO_VALUE = {"OFF": 0, "ON": 1, "AUTO": 2}

    def __init__(
        self,
        entry: ConfigEntry,
        name: str,
        address: int,
        page: int,
        coordinator: Any,
    ) -> None:
        """Initialize the Kronoterm select entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._address = address
        self._page = page

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{address}_mode"
        self._attr_device_info = coordinator.shared_device_info

    @property
    def current_option(self) -> Optional[str]:
        """Return the current option ('OFF', 'ON', or 'AUTO') based on the Modbus register value."""
        modbus_list = extract_modbus_list(self.coordinator.data or {})
        reg = next((r for r in modbus_list if r.get("address") == self._address), None)
        if not reg or reg.get("value") is None:
            return None

        try:
            val = int(float(reg.get("value")))
        except (ValueError, TypeError):
            return None

        return self.VALUE_TO_OPTION.get(val)

    async def async_select_option(self, option: str) -> None:
        """
        Map the selected option to its corresponding register value and update the mode.
        
        Logs an error if the option is unknown or if updating fails.
        """
        new_mode = self.OPTION_TO_VALUE.get(option)
        if new_mode is None:
            _LOGGER.warning("Unknown option: %s", option)
            return

        success = await self.coordinator.async_set_loop_mode_by_page(self._page, new_mode)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set mode for %s", self._attr_name)

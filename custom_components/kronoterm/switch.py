import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Kronoterm switches based on config entry."""
    coordinator = hass.data[DOMAIN].get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    # Define switch configurations
    switch_configs = [
        {
            "name": "Heat Pump ON/OFF",
            "unique_id_suffix": "heatpump_switch",
            "register_address": 2000,
            "get_state_method": lambda c: _get_modbus_register_value(c.data, 2000),
            "turn_on_method": lambda c: c.async_set_heatpump_state(True),
            "turn_off_method": lambda c: c.async_set_heatpump_state(False),
        },
        {
            "name": "DHW Circulation ON/OFF",
            "unique_id_suffix": "dhw_circulation_switch",
            "register_address": 2028,
            "get_state_method": lambda c: _get_modbus_register_value(c.data, 2028),
            "turn_on_method": lambda c: c.async_set_dhw_circulation(True),
            "turn_off_method": lambda c: c.async_set_dhw_circulation(False),
        },
        {
            "name": "Fast Water Heating",
            "unique_id_suffix": "fast_heating_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "fast_water_heating"),
            "turn_on_method": lambda c: c.async_set_fast_water_heating(True),
            "turn_off_method": lambda c: c.async_set_fast_water_heating(False),
        },
        {
            "name": "Antilegionella",
            "unique_id_suffix": "antilegionella_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "antilegionella"),
            "turn_on_method": lambda c: c.async_set_antilegionella(True),
            "turn_off_method": lambda c: c.async_set_antilegionella(False),
        },
    ]

    # Create switch entities
    entities = [
        KronotermSwitch(
            entry,
            coordinator,
            config["name"],
            config["unique_id_suffix"],
            config["get_state_method"],
            config["turn_on_method"],
            config["turn_off_method"],
        )
        for config in switch_configs
    ]

    async_add_entities(entities)
    return True


def _get_modbus_register_value(data: Optional[Dict[str, Any]], address: int) -> bool:
    """Extract a value from modbus registers in the coordinator data."""
    if not data:
        return False
    
    main_data = data.get("main", {})
    modbus_list = main_data.get("ModbusReg", [])
    
    reg = next((r for r in modbus_list if r.get("address") == address), None)
    if not reg:
        return False
        
    return bool(reg.get("value", 0))


def _get_shortcuts_value(data: Optional[Dict[str, Any]], key: str) -> bool:
    """Extract a value from shortcuts data in the coordinator data."""
    if not data:
        return False
        
    shortcuts = data.get("ShortcutsData", {})
    return bool(shortcuts.get(key, 0))


class KronotermSwitch(CoordinatorEntity, SwitchEntity):
    """Generic implementation of Kronoterm switch."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id_suffix: str,
        get_state_method: Callable,
        turn_on_method: Callable,
        turn_off_method: Callable,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._get_state = get_state_method
        self._turn_on = turn_on_method
        self._turn_off = turn_off_method

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{unique_id_suffix}"
        self._attr_name = name
        self._attr_device_info = coordinator.shared_device_info
        self._attr_has_entity_name = True  # Use the device name as a prefix

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if the coordinator has data and is not in an error state
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        try:
            return self._get_state(self.coordinator)
        except Exception as err:
            _LOGGER.error("Error determining switch state: %s", err)
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            success = await self._turn_on(self.coordinator)
            if success:
                # Only refresh if the API call was successful
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to turn on %s via Kronoterm API", self.name)
        except Exception as err:
            _LOGGER.error("Error turning on %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            success = await self._turn_off(self.coordinator)
            if success:
                # Only refresh if the API call was successful
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to turn off %s via Kronoterm API", self.name)
        except Exception as err:
            _LOGGER.error("Error turning off %s: %s", self.name, err)
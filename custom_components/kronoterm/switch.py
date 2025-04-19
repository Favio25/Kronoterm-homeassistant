import logging
from typing import Any, Callable, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory  # Added missing import
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

    # --- Remove register_address and use the 'ShortcutsData' states instead ---
    switch_configs = [
        {
            "name": "heatpump_switch",  # Translation key instead of "ON/OFF"
            "unique_id_suffix": "heatpump_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "heatpump_on"),
            "turn_on_method": lambda c: c.async_set_heatpump_state(True),
            "turn_off_method": lambda c: c.async_set_heatpump_state(False),
        },
        {
            "name": "dhw_circulation_switch",  # Translation key
            "unique_id_suffix": "dhw_circulation_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "circulation_on"),
            "turn_on_method": lambda c: c.async_set_dhw_circulation(True),
            "turn_off_method": lambda c: c.async_set_dhw_circulation(False),
        },
        {
            "name": "fast_heating_switch",  # Translation key
            "unique_id_suffix": "fast_heating_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "fast_water_heating"),
            "turn_on_method": lambda c: c.async_set_fast_water_heating(True),
            "turn_off_method": lambda c: c.async_set_fast_water_heating(False),
        },
        {
            "name": "antilegionella_switch",  # Translation key
            "unique_id_suffix": "antilegionella_switch",
            "get_state_method": lambda c: _get_shortcuts_value(c.data, "antilegionella"),
            "turn_on_method": lambda c: c.async_set_antilegionella(True),
            "turn_off_method": lambda c: c.async_set_antilegionella(False),
        },
    ]

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
    
    # Add the Loop1TemperatureSourceSwitch entity
    entities.append(Loop1TemperatureSourceSwitch(coordinator))
    #entities.append(ReservoirEntitySwitch(coordinator))

    async_add_entities(entities)
    return True


def _get_shortcuts_value(data: Optional[Dict[str, Any]], key: str) -> bool:
    """Extract a boolean state from the 'ShortcutsData' in the coordinator data."""
    if not data:
        return False

    shortcuts = data.get("shortcuts", {})
    # If your coordinator merges them under data["shortcuts"] -> data["ShortcutsData"]
    # then adapt the path accordingly:
    shortcuts_data = shortcuts.get("ShortcutsData", {})
    return bool(shortcuts_data.get(key, 0))


class KronotermSwitch(CoordinatorEntity, SwitchEntity):
    """Generic Kronoterm switch based on the shortcuts response."""

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
        self._attr_translation_key = name
        self._attr_device_info = coordinator.shared_device_info
        self._attr_has_entity_name = True  # Use the device name as a prefix

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        try:
            return self._get_state(self.coordinator)
        except Exception as err:
            _LOGGER.error("Error determining switch state for %s: %s", self.name, err)
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            success = await self._turn_on(self.coordinator)
            if success:
                # Triggers an immediate coordinator refresh so the UI updates right away
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
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to turn off %s via Kronoterm API", self.name)
        except Exception as err:
            _LOGGER.error("Error turning off %s: %s", self.name, err)


class Loop1TemperatureSourceSwitch(SwitchEntity):
    """
    Switch entity for toggling the Loop1 temperature data source.
    This appears under "Configuration" in the device page.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        """Initialize the switch entity to control the Loop1 temperature source."""
        self._coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_translation_key = "loop1_temp_source_switch"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_loop1_data_source"
        
        # Set icon based on function
        self._attr_icon = "mdi:source-branch"

    @property
    def device_info(self):
        """Return the same device info as the coordinator so it appears under the same device."""
        return self._coordinator.shared_device_info

    @property
    def is_on(self) -> bool:
        """Return true if Loop1 data is being used (instead of Modbus)."""
        # Get from config entry options, default to "modbus" (False)
        options = self._coordinator.config_entry.options
        source_str = options.get("loop1_temp_source", "modbus")
        
        # Return True if using loop1_data, False if using modbus
        return source_str == "loop1_data"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on = use Loop1 data for temperature source."""
        await self._update_source("loop1_data")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off = use Modbus for temperature source."""
        await self._update_source("modbus")
    
    async def _update_source(self, source: str) -> None:
        """Update the temperature source and notify relevant entities."""
        _LOGGER.info("User set Loop1 temperature source to: %s", source)

        # Persist in config entry options
        new_options = dict(self._coordinator.config_entry.options)
        new_options["loop1_temp_source"] = source
        self.hass.config_entries.async_update_entry(
            self._coordinator.config_entry, options=new_options
        )
        
        # Notify climate entity to reload
        self.hass.bus.async_fire(f"{DOMAIN}_loop1_source_changed", {"source": source})

class ReservoirEntitySwitch(SwitchEntity):
    """Switch entity to enable or disable the reservoir climate entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        """Initialize the reservoir enable/disable switch."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_reservoir_entity_switch"
        self._attr_translation_key = "reservoir_entity_switch"
        self._attr_icon = "mdi:water"

    # +++ ADD THIS PROPERTY +++
    @property
    def device_info(self):
        """Return the device info of the coordinator."""
        # Ensure the coordinator has the necessary device info attribute
        # Adjust 'shared_device_info' if your coordinator uses a different name
        if hasattr(self._coordinator, 'shared_device_info'):
            return self._coordinator.shared_device_info
        return None
    # +++ END OF ADDITION +++

    @property
    def is_on(self) -> bool:
        """Return the current state from config options."""
        # Default to True if the option is not defined.
        return self._coordinator.config_entry.options.get("reservoir_enabled", True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the reservoir (i.e. set reservoir_enabled to True)."""
        await self._update_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the reservoir (i.e. set reservoir_enabled to False)."""
        await self._update_enabled(False)

    async def _update_enabled(self, enabled: bool) -> None:
        """Update the config option and fire an event for change handling."""
        _LOGGER.info("User set Reservoir Enabled: %s", enabled)
        new_options = dict(self._coordinator.config_entry.options)
        new_options["reservoir_enabled"] = enabled
        # Update the config entry so the option persists.
        self.hass.config_entries.async_update_entry(
            self._coordinator.config_entry, options=new_options
        )
        # Optionally fire an event that other parts of your integration can listen to.
        self.hass.bus.async_fire(f"{DOMAIN}_reservoir_enabled_changed", {"enabled": enabled})
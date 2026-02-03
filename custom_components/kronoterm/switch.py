import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SwitchConfig:
    """Configuration for a Kronoterm shortcut switch."""
    name: str  # translation key
    unique_id_suffix: str
    json_key: str  # key in ShortcutsData
    set_method_name: str # method name on coordinator


def _get_shortcuts_value(data: Optional[Dict[str, Any]], key: str) -> bool:
    """Extract a boolean state from the 'ShortcutsData' in the coordinator data."""
    if not data:
        return False

    shortcuts = data.get("shortcuts", {})
    shortcuts_data = shortcuts.get("ShortcutsData", {})
    
    # Return bool(value) - handles 0/1 or True/False
    return bool(shortcuts_data.get(key, 0))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Kronoterm switches based on config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    _LOGGER.warning("🔥 SWITCH PLATFORM SETUP - Coordinator type: %s, Entry: %s", 
                   type(coordinator).__name__ if coordinator else "None", entry.entry_id)
    
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    # Define all switches that read from the 'ShortcutsData' blob
    switch_configs = [
        SwitchConfig(
            "heatpump_switch",
            "heatpump_switch",
            "heatpump_on",
            "async_set_heatpump_state",
        ),
        SwitchConfig(
            "dhw_circulation_switch",
            "dhw_circulation_switch",
            "circulation_on",
            "async_set_dhw_circulation",
        ),
        SwitchConfig(
            "fast_heating_switch",
            "fast_heating_switch",
            "fast_water_heating",  # Note: key in JSON is different from method
            "async_set_fast_water_heating",
        ),
        SwitchConfig(
            "antilegionella_switch",
            "antilegionella_switch",
            "antilegionella",
            "async_set_antilegionella",
        ),
        SwitchConfig(
            "reserve_source_switch",
            "reserve_source_switch",
            "reserve_source",
            "async_set_reserve_source",
        ),
        SwitchConfig(
            "additional_source_switch",
            "additional_source_switch",
            "additional_source",
            "async_set_additional_source",
        ),
    ]

    entities = [
        KronotermSwitch(entry, coordinator, config)
        for config in switch_configs
    ]
    
    # Add config-specific switches
    # entities.append(ReservoirEntitySwitch(coordinator))

    async_add_entities(entities, update_before_add=True)
    return True


class KronotermSwitch(CoordinatorEntity, SwitchEntity):
    """Generic Kronoterm switch based on the shortcuts response."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        config: SwitchConfig,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._config = config

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{config.unique_id_suffix}"
        self._attr_translation_key = config.name
        self._attr_device_info = coordinator.shared_device_info
        self._attr_has_entity_name = True  # Use the device name as a prefix

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # We also check if the 'shortcuts' key exists in data
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get("shortcuts") is not None
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on, based on coordinator's data."""
        return _get_shortcuts_value(self.coordinator.data, self._config.json_key)

    async def _async_set_state(self, state: bool) -> None:
        """Helper to call the correct coordinator method."""
        try:
            # Get the method from the coordinator by its name
            method_to_call = getattr(self.coordinator, self._config.set_method_name)
            
            # Call the method (e.g., self.coordinator.async_set_heatpump_state(True))
            await method_to_call(state)
            
        except AttributeError:
            _LOGGER.error(
                "Coordinator is missing method: %s", self._config.set_method_name
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting %s to %s: %s", self.name, state, err
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state(True)
        # No refresh needed; the coordinator's set method handles it.

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state(False)
        # No refresh needed; the coordinator's set method handles it.


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

    @property
    def device_info(self):
        """Return the device info of the coordinator."""
        # Ensure the coordinator has the necessary device info attribute
        if hasattr(self._coordinator, 'shared_device_info'):
            return self._coordinator.shared_device_info
        return None

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
            self_coordinator.config_entry, options=new_options
        )
        # Optionally fire an event that other parts of your integration can listen to.
        self.hass.bus.async_fire(f"{DOMAIN}_reservoir_enabled_changed", {"enabled": enabled})
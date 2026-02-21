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
    _LOGGER.debug("Switch platform setup - Coordinator type: %s, Entry: %s", 
                   type(coordinator).__name__ if coordinator else "None", entry.entry_id)
    
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    entities = []
    
    # Check if this is Modbus or Cloud coordinator
    is_modbus = type(coordinator).__name__ == "ModbusCoordinator"
    
    if is_modbus:
        # Modbus switches read from binary registers (official documentation)
        from .entities import KronotermModbusBase
        
        # System On/Off - register 2012 (CORRECTED from 2002)
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2012, "heatpump_switch",
            "async_set_heatpump_state"
        ))
        
        # Fast DHW Heating - register 2015
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2015, "fast_heating_switch", 
            "async_set_fast_water_heating"
        ))
        
        # Additional Source - register 2016
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2016, "additional_source_switch",
            "async_set_additional_source"
        ))
        
        # Reserve Source - register 2018 (NEW - was missing!)
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2018, "reserve_source_switch",
            "async_set_reserve_source"
        ))
        
        # Anti-Legionella - register 2301
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2301, "antilegionella_switch",
            "async_set_antilegionella"
        ))
        
        # DHW Circulation - register 2328
        entities.append(KronotermModbusSwitch(
            entry, coordinator, 2328, "dhw_circulation_switch",
            "async_set_dhw_circulation"
        ))
        
        _LOGGER.debug("Created %d Modbus switches", len(entities))
    else:
        # Cloud API switches read from ShortcutsData
        is_dhw = getattr(coordinator, "system_type", "cloud") == "dhw"
        if is_dhw:
            switch_configs = [
                SwitchConfig(
                    "dhw_luxury_shower",
                    "dhw_luxury_shower",
                    "luxury_shower_status",
                    "async_set_luxury_shower",
                ),
                SwitchConfig(
                    "dhw_antilegionella",
                    "dhw_antilegionella",
                    "antilegionela_status",
                    "async_set_antilegionella",
                ),
                SwitchConfig(
                    "dhw_reserve_source",
                    "dhw_reserve_source",
                    "reserve_source_status",
                    "async_set_reserve_source",
                ),
                SwitchConfig(
                    "dhw_holiday",
                    "dhw_holiday",
                    "holiday_status",
                    "async_set_holiday",
                ),
            ]
        else:
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
                    "fast_water_heating",
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

    async_add_entities(entities, update_before_add=False)
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

class KronotermModbusSwitch(SwitchEntity):
    """Switch entity for Modbus TCP (reads from register, writes via coordinator)."""
    
    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        address: int,
        translation_key: str,
        set_method_name: str,
    ) -> None:
        """Initialize the Modbus switch."""
        self._coordinator = coordinator
        self._entry = entry
        self._address = address
        self._set_method_name = set_method_name
        
        # Use translation_key-based unique_id to match Cloud API format (prevents duplicates on reconfigure)
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{translation_key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = coordinator.shared_device_info
        self._attr_has_entity_name = True
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self._coordinator.last_update_success
            and self._coordinator.data is not None
        )
    
    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        if not self._coordinator.data:
            return False
        
        # Get value from Modbus register
        modbus_list = self._coordinator.data.get("main", {}).get("ModbusReg", [])
        for reg in modbus_list:
            if reg.get("address") == self._address:
                raw_value = reg.get("raw", 0)
                # Binary registers: 1 = on, 0 = off
                return bool(raw_value)
        
        return False
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            method_to_call = getattr(self._coordinator, self._set_method_name)
            success = await method_to_call(True)
            if success:
                await self._coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to turn on %s", self._attr_translation_key)
        except AttributeError:
            _LOGGER.error(
                "Coordinator is missing method: %s", self._set_method_name
            )
        except Exception as err:
            _LOGGER.error("Error turning on %s: %s", self._attr_translation_key, err)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            method_to_call = getattr(self._coordinator, self._set_method_name)
            success = await method_to_call(False)
            if success:
                await self._coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to turn off %s", self._attr_translation_key)
        except AttributeError:
            _LOGGER.error(
                "Coordinator is missing method: %s", self._set_method_name
            )
        except Exception as err:
            _LOGGER.error("Error turning off %s: %s", self._attr_translation_key, err)

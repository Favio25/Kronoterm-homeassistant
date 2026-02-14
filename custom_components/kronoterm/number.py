"""number.py - Defines Number entities for offsets and for coordinator update interval."""

import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN
from .entities import KronotermModbusBase

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------
# OFFSET ENTITIES CONFIGURATION
# ---------------------------------------
@dataclass
class OffsetConfig:
    name: str  # This is the translation_key
    page: int
    address: int
    param_name: str
    min_value: float
    max_value: float
    install_flag: str  # Coordinator attribute to check (e.g., "loop1_installed")

OFFSET_CONFIGS: List[OffsetConfig] = [
    # Loop 1
    OffsetConfig("loop_1_eco_offset", 5, 2047, "circle_eco_offset", -10.0, 0.0, "loop1_installed"),
    OffsetConfig("loop_1_comfort_offset", 5, 2048, "circle_comfort_offset", 0.0, 10.0, "loop1_installed"),
    # Loop 2
    OffsetConfig("loop_2_eco_offset", 6, 2057, "circle_eco_offset", -10.0, 0.0, "loop2_installed"),
    OffsetConfig("loop_2_comfort_offset", 6, 2058, "circle_comfort_offset", 0.0, 10.0, "loop2_installed"),
    # Loop 3
    OffsetConfig("loop_3_eco_offset", 7, 2067, "circle_eco_offset", -10.0, 0.0, "loop3_installed"),
    OffsetConfig("loop_3_comfort_offset", 7, 2068, "circle_comfort_offset", 0.0, 10.0, "loop3_installed"),
    # Loop 4
    OffsetConfig("loop_4_eco_offset", 8, 2077, "circle_eco_offset", -10.0, 0.0, "loop4_installed"),
    OffsetConfig("loop_4_comfort_offset", 8, 2078, "circle_comfort_offset", 0.0, 10.0, "loop4_installed"),
    # Sanitary (DHW)
    OffsetConfig("dhw_eco_offset", 9, 2030, "circle_eco_offset", -10.0, 0.0, "tap_water_installed"), 
    OffsetConfig("dhw_comfort_offset", 9, 2031, "circle_comfort_offset", 0.0, 10.0, "tap_water_installed"),
    # Heat Pump
    OffsetConfig("hp_eco_offset", 0, 2040, "hp_eco_offset", -10.0, 0.0, "loop1_installed"),  # Always available with loop1
    OffsetConfig("hp_comfort_offset", 0, 2041, "hp_comfort_offset", 0.0, 10.0, "loop1_installed"),
    # Pool
    OffsetConfig("pool_eco_offset", 10, 2086, "circle_eco_offset", -10.0, 0.0, "pool_installed"),
    OffsetConfig("pool_comfort_offset", 10, 2087, "circle_comfort_offset", 0.0, 10.0, "pool_installed"),
]


class KronotermOffsetNumber(KronotermModbusBase, NumberEntity):
    """
    A Number entity that represents an ECO/COMFORT offset for a loop or DHW.
    
    Reads the current value from the Modbus register via KronotermModbusBase and
    writes a new value using coordinator.async_set_offset().
    """

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        page: int,
        address: int,
        param_name: str,
        min_value: float,
        max_value: float,
    ) -> None:
        """Initialize the offset number entity."""
        super().__init__(coordinator, address, name, coordinator.shared_device_info)
        
        self._entry = entry
        self._page = page
        self._param_name = param_name

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{page}_{address}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 0.1
        self._attr_unit_of_measurement = "°C"
        self._attr_mode = NumberMode.BOX

    def _process_value(self, raw_value: Any) -> Optional[float]:
        """Convert raw_value to float, remove non-numeric chars."""
        if isinstance(raw_value, str):
            raw_value = re.sub(r"[^\d\.\-]", "", raw_value)

        if raw_value == "":
            return None

        try:
            return float(raw_value)
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Invalid value %s at register %s for %s: %s", 
                raw_value, self._address, self._attr_translation_key, e
            )
            return None

    @property
    def native_value(self) -> Optional[float]:
        return self._compute_value()

    async def async_set_native_value(self, value: float) -> None:
        """Called by HA to set a new offset value."""
        new_offset = round(value, 1)
        success = await self.coordinator.async_set_offset(
            page=self._page,
            param_name=self._param_name,
            new_value=new_offset,
        )
        if not success:
            _LOGGER.error("Failed to update offset for %s to %.1f", self._attr_translation_key, new_offset)
        else:
            _LOGGER.debug("Successfully set %s => %.1f °C", self._attr_translation_key, new_offset)


# ---------------------------------------
# MAIN TEMP OFFSET ENTITY (Refined)
# ---------------------------------------
class KronotermMainOffsetNumber(CoordinatorEntity, NumberEntity):
    """
    System temperature offset number entity.
    
    Works for both Cloud API and Modbus TCP coordinators:
    - Cloud: Reads/writes 'system_temperature_correction' via API
    - Modbus: Reads/writes register 2014
    """
    
    _attr_has_entity_name = True
    _attr_translation_key = "main_temperature_offset"
    _attr_native_min_value = -4.0
    _attr_native_max_value = 4.0
    _attr_native_step = 1.0
    _attr_unit_of_measurement = "°C"
    _attr_icon = "mdi:thermometer-plus"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_main_temp_offset"
        self._device_info = coordinator.shared_device_info
        
        # Determine if this is a Modbus coordinator
        self._is_modbus = hasattr(coordinator, 'register_map') and coordinator.register_map is not None

    @property
    def device_info(self):
        return self._device_info

    @property
    def native_value(self) -> Optional[float]:
        """Read system temperature correction value."""
        if not self.coordinator.data:
            return None
        
        if self._is_modbus:
            # Modbus: Read from register 2014
            modbus_list = self.coordinator.data.get("main", {}).get("ModbusReg", [])
            for reg in modbus_list:
                if reg.get("address") == 2014:
                    raw_value = reg.get("value")
                    if raw_value is not None:
                        try:
                            # Register 2014: scale x 1°C (already scaled by coordinator)
                            return float(raw_value)
                        except (ValueError, TypeError):
                            pass
            return None
        else:
            # Cloud API: Read from AdvancedSettings
            settings_data = self.coordinator.data.get("main_settings", {})
            if not settings_data:
                return None

            raw = None
            advanced = settings_data.get("AdvancedSettings", {})
            if "system_temperature_correction" in advanced:
                 raw = advanced["system_temperature_correction"]

            if raw is not None:
                try:
                    return float(raw)
                except (ValueError, TypeError):
                    pass
                    
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the system temperature correction value."""
        _LOGGER.info("Setting system temperature offset to %s", value)
        
        if self._is_modbus:
            # Modbus: Write to register 2014
            # Register expects integer (scale x 1°C)
            register_value = int(value)
            
            if hasattr(self.coordinator, 'write_register_by_address'):
                success = await self.coordinator.write_register_by_address(2014, register_value)
                if success:
                    await self.coordinator.async_request_refresh()
                else:
                    _LOGGER.error("Failed to write system temperature offset to register 2014")
            else:
                _LOGGER.error("Coordinator missing write_register_by_address method")
        else:
            # Cloud API: Use async_set_main_temp_offset
            await self.coordinator.async_set_main_temp_offset(value)


# ---------------------------------------
# GENERIC MODBUS WRITABLE NUMBER
# ---------------------------------------
class KronotermModbusNumber(KronotermModbusBase, NumberEntity):
    """Generic writable Modbus register number entity."""
    
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: Optional[str],
        device_info: dict,
        scale: float = 1.0,
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._scale = scale
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_mode = NumberMode.BOX
        self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_modbus_number_{address}"
    
    @property
    def unique_id(self) -> str:
        return self._unique_id
    
    @property
    def native_value(self) -> Optional[float]:
        """Get current value from Modbus."""
        raw_value = self._get_modbus_value()
        if raw_value is None:
            return None
        
        try:
            val = float(raw_value)
            if self._scale != 1.0:
                val *= self._scale
            return round(val, 2)
        except (ValueError, TypeError):
            return None
    
    async def async_set_native_value(self, value: float) -> None:
        """Write value to Modbus register."""
        # Convert to register value (apply inverse scaling)
        register_value = int(value / self._scale) if self._scale != 1.0 else int(value)
        
        _LOGGER.info("Setting %s (register %d) to %.1f (raw: %d)", 
                    self._name_key, self._address, value, register_value)
        
        # Write via coordinator
        if hasattr(self._coordinator, 'write_register_by_address'):
            success = await self._coordinator.write_register_by_address(self._address, register_value)
            if success:
                await self._coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to write register %d", self._address)
        else:
            _LOGGER.error("Coordinator missing write_register_by_address method")


# ---------------------------------------
# COORDINATOR INTERVAL ENTITY
# ---------------------------------------
class CoordinatorUpdateIntervalNumber(NumberEntity):
    """
    Number entity for configuring the coordinator update interval (in seconds).
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 5      # 5 seconds minimum (faster than batch read time)
    _attr_native_max_value = 600    # 10 minutes maximum
    _attr_native_step = 5           # 5 second increments
    _attr_mode = NumberMode.BOX
    _attr_unit_of_measurement = "s"

    def __init__(self, coordinator):
        self._coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_translation_key = "update_interval"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_update_interval"

    @property
    def device_info(self):
        return self._coordinator.shared_device_info

    @property
    def native_value(self) -> float:
        if self._coordinator.update_interval:
            return self._coordinator.update_interval.total_seconds()
        return 300.0  # 5 minutes default (in seconds)

    async def async_set_native_value(self, value: float) -> None:
        seconds = max(5, min(int(value), 600))  # Clamp between 5s and 600s
        _LOGGER.info("User set coordinator update interval to %s seconds", seconds)

        from datetime import timedelta
        self._coordinator.update_interval = timedelta(seconds=seconds)

        new_options = dict(self._coordinator.config_entry.options)
        new_options["scan_interval_seconds"] = seconds  # Store in seconds now
        # Keep old "scan_interval" for backwards compatibility (in minutes)
        new_options["scan_interval"] = max(1, int(seconds / 60))
        self.hass.config_entries.async_update_entry(
            self._coordinator.config_entry, options=new_options
        )
        await self._coordinator.async_request_refresh()


# ---------------------------------------
# SETUP PLATFORM
# ---------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Number entities."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    _LOGGER.debug("Number platform setup - Coordinator type: %s, Entry: %s", 
                   type(coordinator).__name__ if coordinator else "None", entry.entry_id)
    
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found in hass.data[%s]", DOMAIN)
        return

    entities = []

    # Get the list of all addresses reported by the heat pump
    modbus_list = (coordinator.data or {}).get("main", {}).get("ModbusReg", [])
    available_addresses = {reg.get("address") for reg in modbus_list}
    
    _LOGGER.debug("Coordinator data keys: %s", list((coordinator.data or {}).keys()))
    _LOGGER.debug("Modbus list length: %d", len(modbus_list))
    _LOGGER.debug("Available addresses (first 10): %s", sorted(list(available_addresses))[:10])

    # 1) Create standard Modbus offset entities
    for config in OFFSET_CONFIGS:
        is_installed = getattr(coordinator, config.install_flag, False)
        is_available = config.address in available_addresses
        
        _LOGGER.debug("Checking %s (addr %d): installed=%s, available=%s", 
                       config.name, config.address, is_installed, is_available)

        if is_installed and is_available:
            entities.append(
                KronotermOffsetNumber(
                    entry=entry,
                    coordinator=coordinator,
                    name=config.name,
                    page=config.page,
                    address=config.address,
                    param_name=config.param_name,
                    min_value=config.min_value,
                    max_value=config.max_value,
                )
            )
            _LOGGER.debug("Created entity for %s", config.name)

    # 2) Create the coordinator update interval entity
    entities.append(CoordinatorUpdateIntervalNumber(coordinator))
    _LOGGER.debug("Added update interval entity")

    # 3) Create the System Temperature Offset entity (works for both Cloud and Modbus)
    entities.append(KronotermMainOffsetNumber(coordinator, entry))
    _LOGGER.debug("Added system temperature offset entity")

    _LOGGER.info("Created %d number entities", len(entities))
    async_add_entities(entities, update_before_add=False)
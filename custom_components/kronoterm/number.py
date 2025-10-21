"""number.py - Defines Number entities for offsets and for coordinator update interval."""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entities import KronotermModbusBase

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------
# OFFSET ENTITIES
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
    # Sanitary (DHW)
    OffsetConfig("dhw_eco_offset", 9, 2030, "circle_eco_offset", -10.0, 0.0, "tap_water_installed"), # Assuming 'tap_water_installed' flag exists
    OffsetConfig("dhw_comfort_offset", 9, 2031, "circle_comfort_offset", 0.0, 10.0, "tap_water_installed"), # Assuming 'tap_water_installed' flag exists
    
    OffsetConfig("loop_3_eco_offset", 7, 2067, "circle_eco_offset", -10.0, 0.0, "loop3_installed"),
    OffsetConfig("loop_3_comfort_offset", 7, 2068, "circle_comfort_offset", 0.0, 10.0, "loop3_installed"),

    OffsetConfig("loop_4_eco_offset", 8, 2077, "circle_eco_offset", -10.0, 0.0, "loop4_installed"),
    OffsetConfig("loop_4_comfort_offset", 8, 2078, "circle_comfort_offset", 0.0, 10.0, "loop4_installed"),
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
        # Pass coordinator, address, name, and device_info to the base class
        super().__init__(coordinator, address, name, coordinator.shared_device_info)
        
        # Store entity-specific attributes
        self._entry = entry
        self._page = page
        self._param_name = param_name

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{page}_{address}"

        # Define numeric bounds.
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 0.1
        self._attr_unit_of_measurement = "°C"  # offset in Celsius

    def _process_value(self, raw_value: Any) -> Optional[float]:
        """Convert raw_value to float, remove non-numeric chars."""
        if isinstance(raw_value, str):
            # Use regex to strip units and non-numeric characters
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
        """Return the current offset value by calling the base class's compute method."""
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
# COORDINATOR INTERVAL ENTITY
# (This class is self-contained and does not need refactoring)
# ---------------------------------------
class CoordinatorUpdateIntervalNumber(NumberEntity):
    """
    Number entity for configuring the coordinator update interval (in minutes).
    This appears under "Configuration" in the device page.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_mode = NumberMode.AUTO
    _attr_unit_of_measurement = "min"

    def __init__(self, coordinator):
        """Initialize the number entity to control the coordinator update interval."""
        self._coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_translation_key = "update_interval"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_update_interval"

    @property
    def device_info(self):
        """Return the same device info as the coordinator so it appears under the same device."""
        return self._coordinator.shared_device_info

    @property
    def native_value(self) -> float:
        """Return the current update interval in minutes."""
        if self._coordinator.update_interval:
            return self._coordinator.update_interval.total_seconds() / 60.0
        return 5.0  # fallback if no update_interval is set

    async def async_set_native_value(self, value: float) -> None:
        """Handle user changes from the HA UI slider/field."""
        minutes = max(1, min(int(value), 60))  # clamp to [1..60]
        _LOGGER.info("User set coordinator update interval to %s minutes", minutes)

        # 1) Update the coordinator in-memory
        from datetime import timedelta
        self._coordinator.update_interval = timedelta(minutes=minutes)

        # 2) Persist in config entry options so it survives restarts
        new_options = dict(self._coordinator.config_entry.options)
        new_options["scan_interval"] = minutes
        self.hass.config_entries.async_update_entry(
            self._coordinator.config_entry, options=new_options
        )

        # 3) Optionally request an immediate refresh:
        await self._coordinator.async_request_refresh()


# ---------------------------------------
# SETUP PLATFORM
# ---------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Number entities for offsets AND the coordinator update interval."""
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found in hass.data[%s]", DOMAIN)
        return

    entities = []

    # Get the list of all addresses reported by the heat pump
    modbus_list = (coordinator.data or {}).get("main", {}).get("ModbusReg", [])
    available_addresses = {reg.get("address") for reg in modbus_list}

    # 1) Create offset entities
    for config in OFFSET_CONFIGS:
        # Check if the feature is installed (e.g., coordinator.loop1_installed)
        is_installed = getattr(coordinator, config.install_flag, False)
        
        # Check if the specific Modbus address is reported by the pump
        is_available = config.address in available_addresses

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
        else:
            _LOGGER.info(
                "Skipping entity %s: Installed=%s, Address %s Available=%s",
                config.name,
                is_installed,
                config.address,
                is_available,
            )

    # 2) Create the coordinator update interval entity
    entities.append(CoordinatorUpdateIntervalNumber(coordinator))

    # 3) Register them with Home Assistant
    async_add_entities(entities, update_before_add=True)
"""number.py - Defines Number entities for ECO/COMFORT offsets on three loops."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define a configuration data class for offset entities.
@dataclass
class OffsetConfig:
    name: str
    page: int
    address: int
    param_name: str
    min_value: float
    max_value: float

# Define configurations for each offset entity.
OFFSET_CONFIGS: List[OffsetConfig] = [
    # Loop 1
    OffsetConfig("Loop 1 ECO Offset", 5, 2047, "circle_eco_offset", -10.0, 0.0),
    OffsetConfig("Loop 1 COMFORT Offset", 5, 2048, "circle_comfort_offset", 0.0, 10.0),
    # Loop 2
    OffsetConfig("Loop 2 ECO Offset", 6, 2057, "circle_eco_offset", -10.0, 0.0),
    OffsetConfig("Loop 2 COMFORT Offset", 6, 2058, "circle_comfort_offset", 0.0, 10.0),
    # Sanitary (DHW)
    OffsetConfig("Sanitary ECO Offset", 9, 2030, "circle_eco_offset", -10.0, 0.0),
    OffsetConfig("Sanitary COMFORT Offset", 9, 2031, "circle_comfort_offset", 0.0, 10.0),
]


def get_modbus_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the list of Modbus registers from the coordinator data."""
    return data.get("main", {}).get("ModbusReg", [])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up Number entities for ECO and COMFORT offsets for Loop 1, Loop 2, and Sanitary,
    using a single Kronoterm coordinator.
    """
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found in hass.data[%s]", DOMAIN)
        return

    entities = []
    modbus_list = get_modbus_list(coordinator.data or {})

    for config in OFFSET_CONFIGS:
        # Only add the entity if the corresponding register exists.
        if any(reg.get("address") == config.address for reg in modbus_list):
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
                "Register %s not found for %s, skipping entity creation.",
                config.address,
                config.name,
            )

    async_add_entities(entities, update_before_add=True)


class KronotermOffsetNumber(CoordinatorEntity, NumberEntity):
    """
    A Number entity that represents an ECO/COMFORT offset for a loop or DHW.
    
    Reads the current value from the Modbus register in coordinator.data and writes a new value
    using coordinator.async_set_offset.
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
        super().__init__(coordinator)
        self._entry = entry
        self._page = page
        self._address = address
        self._param_name = param_name

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{page}_{address}"
        self._attr_device_info = coordinator.shared_device_info

        # Define numeric bounds.
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 0.1

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement for offsets (°C)."""
        return "°C"

    @property
    def native_value(self) -> Optional[float]:
        """
        Return the current offset value from the Modbus register at self._address.
        Expected data is in coordinator.data["main"]["ModbusReg"].
        """
        modbus_list = get_modbus_list(self.coordinator.data or {})
        reg = next((x for x in modbus_list if x.get("address") == self._address), None)
        if not reg:
            _LOGGER.debug("Register %s not found for %s", self._address, self._attr_name)
            return None

        raw_val = reg.get("value")
        if raw_val is None:
            return None

        if isinstance(raw_val, str):
            raw_val = raw_val.replace("°C", "").strip()

        try:
            return float(raw_val)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid value %s at register %s for %s", raw_val, self._address, self._attr_name)
            return None

    async def async_set_native_value(self, value: float) -> None:
        """
        Called by Home Assistant to set a new offset value.
        Uses coordinator.async_set_offset() to update the value.
        """
        new_offset = round(value, 1)
        success = await self.coordinator.async_set_offset(
            page=self._page,
            param_name=self._param_name,
            new_value=new_offset,
        )
        if not success:
            _LOGGER.error("Failed to update offset for %s to %.1f", self._attr_name, new_offset)
        else:
            _LOGGER.debug("Successfully set %s => %.1f °C", self._attr_name, new_offset)

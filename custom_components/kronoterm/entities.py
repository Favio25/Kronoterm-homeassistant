"""
entities.py
-----------
This file houses all Kronoterm base entity classes for improved maintainability.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class KronotermModbusBase(CoordinatorEntity):
    """
    Base class for Kronoterm Modbus-based entities.
    It uses a DataUpdateCoordinator to fetch data,
    and expects 'ModbusReg' in coordinator.data["main"].
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        device_info: Dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._address: int = address
        self._name_key: str = name  # Store as translation key
        self._device_info: Dict[str, Any] = device_info
        self._unique_id: Optional[str] = None
        self._attr_has_entity_name = True
        self._attr_translation_key = name  # Set translation key directly
        self._attr_entity_id = f"{DOMAIN}.{name}"

    @property
    def modbus_data(self) -> List[Dict[str, Any]]:
        """
        Safely return modbus data from coordinator.data["main"]["ModbusReg"].
        """
        if not self.coordinator.data:
            return []
        main_data = self.coordinator.data.get("main", {})
        return main_data.get("ModbusReg", [])

    def _get_modbus_value(self) -> Optional[Any]:
        """
        Retrieve the 'value' from the ModbusReg entry for self._address.
        Returns None if not found.
        """
        return next(
            (reg.get("value") for reg in self.modbus_data if reg.get("address") == self._address),
            None,
        )

    def _compute_value(self) -> Optional[Union[float, int, str]]:
        """
        Common routine: retrieve and parse the raw value. Return None if missing/invalid.
        """
        raw_value = self._get_modbus_value()
        if raw_value is None:
            return None
        try:
            return self._process_value(raw_value)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug(
                "Error processing value for address %s (%s): %s",
                self._address,
                self._name_key,
                ex,
            )
            return None

    def _process_value(self, raw_value: Any) -> Any:
        """Default pass-through. Subclasses may override for scaling, etc."""
        return raw_value

    @property
    def should_poll(self) -> bool:
        """Coordinator-based entities do not poll on their own."""
        return False

    @property
    def available(self) -> bool:
        """Available if the last update succeeded and coordinator data is present."""
        # We also check if the specific value is available in the modbus data
        return bool(
            self.coordinator.last_update_success 
            and self.coordinator.data
            and self._get_modbus_value() is not None
        )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device info shared by Kronoterm entities."""
        return self._device_info


class KronotermBinarySensor(KronotermModbusBase, BinarySensorEntity):
    """
    A binary sensor reading an integer from Modbus, optionally checking a specific bit.
    This is defined here so it can be imported by 'binary_sensor.py'
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        device_info: Dict[str, Any],
        bit: Optional[int] = None,
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._bit: Optional[int] = bit
        self._icon: Optional[str] = icon
        suffix = f"_{bit}" if bit is not None else ""
        # Include config entry ID to prevent conflicts with Cloud API integration
        self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_binary_{address}{suffix}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def is_on(self) -> bool:
        """Return True if the register or bit indicates ON."""
        try:
            raw_value = self._get_modbus_value()
            if raw_value is not None:
                int_value = int(raw_value)
                if self._bit is not None:
                    return bool(int_value & (1 << self._bit))
                return bool(int_value)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.error(
                "Error processing binary sensor value for address %s (%s): %s",
                self._address,
                self._name_key,
                ex,
            )
        return False
"""
entities.py
-----------
This file houses all Kronoterm entity classes for improved maintainability.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class KronotermModbusBase(CoordinatorEntity):
    """
    Base class for Kronoterm Modbus-based entities. It extends
    CoordinatorEntity to use the Home Assistant DataUpdateCoordinator mechanism.

    Entities that need to retrieve data from the 'ModbusReg' array
    should inherit from this class for consistent handling of addresses,
    shared device info, and coordinator data.
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
        self._name: str = name
        self._device_info: Dict[str, Any] = device_info
        self._unique_id: Optional[str] = None

    @property
    def modbus_data(self) -> List[Dict[str, Any]]:
        """Safely return modbus data from the coordinator, or an empty list if unavailable."""
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.get("ModbusReg", [])

    def _get_modbus_value(self) -> Optional[float]:
        """
        Retrieve the raw modbus value from 'modbus_data' for the given address.
        Returns None if the address is not found.
        """
        return next(
            (reg.get("value") for reg in self.modbus_data if reg.get("address") == self._address),
            None,
        )

    def _compute_value(self) -> Optional[Union[float, int, str]]:
        """
        Common routine to retrieve and process the raw value.
        Returns None if the value is missing or cannot be processed.
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
                self._name,
                ex,
            )
            return None

    def _process_value(self, raw_value: Any) -> Any:
        """
        Default implementation just returns the raw_value.
        Child classes can override this to implement scaling or other processing.
        """
        return raw_value

    @property
    def should_poll(self) -> bool:
        """Entities using DataUpdateCoordinator should not poll on their own."""
        return False

    @property
    def available(self) -> bool:
        """
        Report entity availability based on whether the last update succeeded
        and if coordinator data is not None.
        """
        return bool(self.coordinator.last_update_success and self.coordinator.data)

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device info for the Kronoterm device."""
        return self._device_info

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self._name


class KronotermModbusRegSensor(KronotermModbusBase, SensorEntity):
    """
    A sensor entity that reads a numeric value (possibly scaled) from the Modbus register data.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        unit: str,
        device_info: Dict[str, Any],
        scale: float = 1.0,
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._scale: float = scale
        self._unit: str = unit
        self._icon: Optional[str] = icon
        self._unique_id = f"{DOMAIN}_modbus_{address}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit of measurement."""
        return self._unit

    def _process_value(self, raw_value: Any) -> Optional[float]:
        """Process and convert raw_value, stripping non-numeric characters if needed."""
        if isinstance(raw_value, str):
            # Remove non-numeric characters (commas, letters, etc.)
            raw_value = re.sub(r"[^\d\.]", "", raw_value)

        numeric_val = float(raw_value)
        if self._scale != 1:
            numeric_val *= self._scale

        # Round to 2 decimals for cleanliness
        return round(numeric_val, 2)

    @property
    def native_value(self) -> Optional[float]:
        """
        Return the state value in Home Assistant's recommended sensor property (`native_value`).
        Returns None if the value cannot be parsed or is unavailable.
        """
        return self._compute_value()


class KronotermBinarySensor(KronotermModbusBase, BinarySensorEntity):
    """
    A binary sensor that reads an integer value from the Modbus register
    and possibly masks out a specific bit to determine 'on/off' state.
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
        self._unique_id = f"{DOMAIN}_binary_{address}{suffix}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def is_on(self) -> bool:
        """Determine if the binary sensor is 'on' based on the raw integer or specific bit."""
        try:
            raw_value = self._get_modbus_value()
            if raw_value is not None:
                if self._bit is not None:
                    return bool(raw_value & (1 << self._bit))
                return bool(raw_value)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.error(
                "Error processing binary sensor value for address %s (%s): %s",
                self._address,
                self._name,
                ex,
            )
        return False


class KronotermEnumSensor(KronotermModbusBase, SensorEntity):
    """
    A sensor entity that maps a raw integer (or similar) to a human-readable text
    via an options dictionary.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        options: Dict[Any, str],
        device_info: Dict[str, Any],
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._options: Dict[Any, str] = options
        self._icon: Optional[str] = icon
        self._unique_id = f"{DOMAIN}_enum_{address}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    def _process_value(self, raw_value: Any) -> Optional[str]:
        """Translate the raw_value via the options map. Return None if not found."""
        return self._options.get(raw_value)

    @property
    def native_value(self) -> Optional[str]:
        """
        Return the translated enum value, or None if the raw value
        was missing or did not match any known option.
        """
        return self._compute_value()

"""
entities.py
-----------
This file houses all Kronoterm entity classes for improved maintainability.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UNKNOWN_VALUE = "unknown"


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
        coordinator: Any,
        address: int,
        name: str,
        device_info: Dict[str, Any]
    ) -> None:
        super().__init__(coordinator)
        self._address: int = address
        self._name: str = name
        self._device_info: Dict[str, Any] = device_info
        self._unique_id: Optional[str] = None

    @property
    def modbus_data(self) -> List[Dict[str, Any]]:
        """Return modbus data from the coordinator."""
        return self.coordinator.data.get("ModbusReg", [])

    def _get_modbus_value(self) -> Optional[Union[int, float]]:
        """Retrieve modbus value from the data for the given address."""
        return next(
            (reg.get("value") for reg in self.modbus_data if reg.get("address") == self._address),
            None
        )

    def _compute_value(self) -> Union[str, float, int]:
        """
        Common routine to retrieve and process raw value,
        returning 'unknown' on error.
        """
        raw_value = self._get_modbus_value()
        if raw_value is None:
            return UNKNOWN_VALUE
        try:
            return self._process_value(raw_value)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.debug("Error processing value for address %s: %s", self._address, ex)
            return UNKNOWN_VALUE

    def _process_value(self, raw_value: Any) -> Any:
        """
        Default implementation just returns raw_value;
        child classes can override this to implement scaling or other processing.
        """
        return raw_value

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def name(self) -> str:
        return self._name


class KronotermModbusRegSensor(KronotermModbusBase, SensorEntity):
    def __init__(
        self,
        coordinator: Any,
        address: int,
        name: str,
        unit: str,
        device_info: Dict[str, Any],
        scale: float = 1,
        icon: Optional[str] = None
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._unit: str = unit
        self._scale: float = scale
        self._icon: Optional[str] = icon
        self._unique_id = f"{DOMAIN}_modbus_{address}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def unit_of_measurement(self) -> str:
        return self._unit

    def _process_value(self, raw_value: Any) -> Union[float, Any]:
        """Apply scaling if necessary."""
        try:
            if self._scale != 1:
                scaled_value: float = float(raw_value) * self._scale
                return round(scaled_value, 2)
            return raw_value
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Error scaling value for sensor %s: %s", self._name, ex)
            return UNKNOWN_VALUE

    @property
    def state(self) -> Union[str, float, int]:
        return self._compute_value()


class KronotermBinarySensor(KronotermModbusBase, BinarySensorEntity):
    def __init__(
        self,
        coordinator: Any,
        address: int,
        name: str,
        device_info: Dict[str, Any],
        bit: Optional[int] = None,
        icon: Optional[str] = None
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._bit: Optional[int] = bit
        self._icon: Optional[str] = icon
        suffix: str = f"_{bit}" if bit is not None else ""
        self._unique_id = f"{DOMAIN}_binary_{address}{suffix}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def is_on(self) -> bool:
        """Determine if the binary sensor is 'on'."""
        try:
            raw_value = self._get_modbus_value()
            if raw_value is not None:
                if self._bit is not None:
                    return bool(raw_value & (1 << self._bit))
                return bool(raw_value)
        except (ValueError, TypeError, AttributeError) as ex:
            _LOGGER.error("Error processing binary sensor value for address %s: %s", self._address, ex)
        return False


class KronotermEnumSensor(KronotermModbusBase, SensorEntity):
    def __init__(
        self,
        coordinator: Any,
        address: int,
        name: str,
        options: Dict[Any, str],
        device_info: Dict[str, Any],
        icon: Optional[str] = None
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

    def _process_value(self, raw_value: Any) -> str:
        """Translate raw_value via the options map."""
        return self._options.get(raw_value, UNKNOWN_VALUE)

    @property
    def state(self) -> Union[str, float, int]:
        return self._compute_value()

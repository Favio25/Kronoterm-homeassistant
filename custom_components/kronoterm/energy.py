import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def _get_daily_energy(trend: Dict[str, List[float]], key: str) -> float:
    """
    Get the current day's energy usage (last entry in the trend array).
    If no data exists, return 0.
    """
    arr = trend.get(key, [])
    if not arr:
        return 0.0
    
    # The last entry is the current day's accumulating value
    return arr[-1]

class KronotermDailyEnergySensor(CoordinatorEntity, SensorEntity):
    """
    Sensor that returns the current day's energy usage for a single consumption key.
    """
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_info: Dict[str, Any],
        data_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_daily_{data_key}"
        self._device_info = device_info
        self._data_key = data_key

        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:flash"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def native_value(self) -> Optional[float]:
        consumption = self.coordinator.data.get("consumption", {})
        trend = consumption.get("trend_consumption", {})
        value = _get_daily_energy(trend, self._data_key)
        return round(value, 3) if value is not None else None

class KronotermDailyEnergyCombinedSensor(CoordinatorEntity, SensorEntity):
    """
    Sensor that sums the current day's energy usage from multiple consumption keys.
    """
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_info: Dict[str, Any],
        data_keys: List[str],
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        joined_keys = "_".join(data_keys)
        self._attr_unique_id = f"{DOMAIN}_daily_combined_{joined_keys}"
        self._device_info = device_info
        self._data_keys = data_keys

        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def native_value(self) -> Optional[float]:
        consumption = self.coordinator.data.get("consumption", {})
        trend = consumption.get("trend_consumption", {})
        total = sum(_get_daily_energy(trend, key) for key in self._data_keys)
        return round(total, 3)
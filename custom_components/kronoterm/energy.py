import logging
from typing import Any, Dict, List, Optional
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.util import dt as dt_util
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
    
    # The last entry is the current day's accumulated value.
    return arr[-1]

class KronotermDailyEnergySensor(CoordinatorEntity, SensorEntity):
    """
    Sensor that returns the current day's energy usage for a single consumption key,
    showing the accumulated value as provided by the API.
    """
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_info: Dict[str, Any],
        data_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = name
        self._attr_unique_id = f"{DOMAIN}_daily_{data_key}"
        self._device_info = device_info
        self._data_key = data_key

        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:flash"
        self._attr_state_class = SensorStateClass.TOTAL

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
    Sensor that sums the current day's energy usage from multiple consumption keys,
    showing the accumulated combined value.
    """
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_info: Dict[str, Any],
        data_keys: List[str],
    ) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = name
        joined_keys = "_".join(data_keys)
        self._attr_unique_id = f"{DOMAIN}_daily_combined_{joined_keys}"
        self._device_info = device_info
        self._data_keys = data_keys

        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def native_value(self) -> Optional[float]:
        consumption = self.coordinator.data.get("consumption", {})
        trend = consumption.get("trend_consumption", {})
        total = sum(_get_daily_energy(trend, key) for key in self._data_keys)
        return round(total, 3)


class KronotermCalculatedCurrentPowerSensor(CoordinatorEntity, SensorEntity):
    """Estimate current power from the rate of change in daily combined energy."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        device_info: Dict[str, Any],
        data_keys: List[str],
    ) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = name
        joined_keys = "_".join(data_keys)
        self._attr_unique_id = f"{DOMAIN}_calculated_power_{joined_keys}"
        self._device_info = device_info
        self._data_keys = data_keys

        self._attr_native_unit_of_measurement = "W"
        self._attr_icon = "mdi:flash"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0.0

        self._last_value: Optional[float] = None
        self._last_time = None
        self._last_date = None

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    def _current_total(self) -> float:
        consumption = self.coordinator.data.get("consumption", {})
        trend = consumption.get("trend_consumption", {})
        return float(sum(_get_daily_energy(trend, key) for key in self._data_keys))

    def _reset_tracking(self, current: float, now) -> None:
        self._last_value = current
        self._last_time = now
        self._last_date = now.date()
        self._attr_native_value = 0.0

    def _handle_coordinator_update(self) -> None:
        now = dt_util.now()
        current = self._current_total()

        if self._last_date and now.date() != self._last_date:
            self._reset_tracking(current, now)
            self.async_write_ha_state()
            return

        if self._last_value is None or self._last_time is None:
            self._reset_tracking(current, now)
            self.async_write_ha_state()
            return

        delta = current - self._last_value
        if delta < 0:
            self._reset_tracking(current, now)
            self.async_write_ha_state()
            return

        hours = (now - self._last_time).total_seconds() / 3600.0
        if hours <= 0:
            self.async_write_ha_state()
            return

        power_w = max(0.0, (delta / hours) * 1000.0)
        self._attr_native_value = round(power_w, 1)
        self._last_value = current
        self._last_time = now
        self._last_date = now.date()
        self.async_write_ha_state()

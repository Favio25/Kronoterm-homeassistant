import logging
import re
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)

from .energy import KronotermDailyEnergySensor, KronotermDailyEnergyCombinedSensor
from .const import (
    DOMAIN,
    SENSOR_DEFINITIONS,
    ENUM_SENSOR_DEFINITIONS,
    SensorDefinition,
    EnumSensorDefinition,
)
from .entities import KronotermModbusBase

_LOGGER = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# SENSOR CLASSES
# -----------------------------------------------------------------------------

class KronotermModbusRegSensor(KronotermModbusBase, SensorEntity):
    """Numeric Modbus register sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        unit: Optional[str],
        device_info: Dict[str, Any],
        scale: float = 1.0,
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._scale = scale
        self._unit = unit
        self._icon = icon
        # Include config entry ID to prevent conflicts with Cloud API integration
        self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_modbus_{address}"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        return self._unit

    def _process_value(self, raw_value: Any) -> Optional[float]:
        if isinstance(raw_value, str):
            raw_value = re.sub(r"[^\d\.\-]", "", raw_value)
        if raw_value == "":
            return None
        val = float(raw_value)
        if self._scale != 1:
            val *= self._scale
        return round(val, 2)

    @property
    def native_value(self) -> Optional[float]:
        return self._compute_value()


class KronotermEnumSensor(KronotermModbusBase, SensorEntity):
    """Enumerated Modbus sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        address: int,
        name: str,
        options: Dict[int, str],
        device_info: Dict[str, Any],
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, address, name, device_info)
        self._options = options
        self._icon = icon
        # Include config entry ID to prevent conflicts with Cloud API integration
        self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_enum_{address}"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(self._options.values())

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def native_value(self) -> Optional[str]:
        raw_value = self._get_modbus_value()
        if raw_value is None:
            return None
        try:
            int_val = int(float(raw_value))
            return self._options.get(int_val)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Could not map enum value '%s' for sensor %s (addr %s)",
                raw_value,
                self._name_key,
                self._address,
            )
            return None


class KronotermJsonSensor(CoordinatorEntity, SensorEntity):
    """Sensor reading nested JSON fields."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: Dict[str, Any],
        unique_id_suffix: str,
        translation_key: str,
        data_path: List[str],
        unit: Optional[str] = None,
        icon: Optional[str] = None,
        device_class: Optional[SensorDeviceClass] = None,
        state_class: Optional[SensorStateClass] = None,
    ) -> None:
        super().__init__(coordinator)
        self._device_info = device_info
        self._data_path = data_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_{unique_id_suffix}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def native_value(self) -> Optional[float]:
        value = self.coordinator.data
        if not value:
            return None
        try:
            for key in self._data_path:
                value = value[key]
            if value is None or value in ("-60.0", "unknown", "unavailable"):
                return None
            if isinstance(value, str):
                value = re.sub(r"[^\d\.\-]", "", value)
                if value == "":
                    return None
            return round(float(value), 2)
        except (KeyError, IndexError, TypeError, ValueError):
            return None


# -----------------------------------------------------------------------------
# SETUP ENTRY
# -----------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found.")
        return False

    device_info = coordinator.shared_device_info
    if not coordinator.data:
        _LOGGER.warning("No data from Kronoterm. Skipping sensors.")
        return False

    all_entities = []
    sensor_entities = []

    for sensor_def in SENSOR_DEFINITIONS:
        # Skip optional features
        if sensor_def.key == "pool_temperature" and not coordinator.pool_installed:
            continue
        if sensor_def.key == "alternative_source_temperature" and not coordinator.alt_source_installed:
            continue

        # Skip sensors if loop not installed
        if sensor_def.key.startswith("loop_1_") and not coordinator.loop1_installed:
            continue
        if sensor_def.key.startswith("loop_2_") and not coordinator.loop2_installed:
            continue
        if sensor_def.key.startswith("loop_3_") and not coordinator.loop3_installed:
            continue
        if sensor_def.key.startswith("loop_4_") and not coordinator.loop4_installed:
            continue

        # Skip thermostat sensors with 0 or missing values
        if sensor_def.key in {
            "loop_1_thermostat_temperature",
            "loop_2_thermostat_temperature",
            "loop_3_thermostat_temperature",
            "loop_4_thermostat_temperature",
        }:
            try:
                modbus = coordinator.data.get("main", {}).get("ModbusReg", [])
                for item in modbus:
                    if item.get("address") == sensor_def.address:
                        raw_value = item.get("value")
                        break
                else:
                    raw_value = None

                if raw_value is None or raw_value == "" or str(raw_value).strip() == "0":
                    _LOGGER.debug(
                        "Skipping thermostat sensor %s (addr %s) due to value=%s",
                        sensor_def.key,
                        sensor_def.address,
                        raw_value,
                    )
                    continue
            except Exception as e:
                _LOGGER.warning(
                    "Could not verify thermostat sensor %s (addr %s): %s",
                    sensor_def.key,
                    sensor_def.address,
                    e,
                )
                continue


        ent = KronotermModbusRegSensor(
            coordinator=coordinator,
            address=sensor_def.address,
            name=sensor_def.key,
            unit=sensor_def.unit,
            device_info=device_info,
            scale=sensor_def.scaling,
            icon=sensor_def.icon,
        )

        if sensor_def.diagnostic:
            ent._attr_entity_category = EntityCategory.DIAGNOSTIC
            

        # Apply device/state classes
        if sensor_def.address == 2362:
            ent._attr_device_class = SensorDeviceClass.ENERGY
            ent._attr_state_class = SensorStateClass.TOTAL
        elif sensor_def.key.endswith("_temperature"):
            ent._attr_device_class = SensorDeviceClass.TEMPERATURE
            ent._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_def.unit == "h":
            ent._attr_device_class = SensorDeviceClass.DURATION
            ent._attr_state_class = SensorStateClass.TOTAL_INCREASING

        sensor_entities.append(ent)

    # Enum sensors
    enum_entities = []
    for enum_def in ENUM_SENSOR_DEFINITIONS:
        ent = KronotermEnumSensor(
            coordinator,
            enum_def.address,
            enum_def.key,
            enum_def.options,
            device_info,
            enum_def.icon,
        )
        if enum_def.diagnostic:
            ent._attr_entity_category = EntityCategory.DIAGNOSTIC
            
        enum_entities.append(ent)

    # JSON loop sensors (loop temperature readings)
    json_entities = []
    for i in range(1, 5):
        if getattr(coordinator, f"loop{i}_installed", False):
            json_entities.append(
                KronotermJsonSensor(
                    coordinator,
                    device_info,
                    f"loop_{i}_temp",
                    f"loop_{i}_temperature",
                    [f"loop{i}", "TemperaturesAndConfig", f"heating_circle_{i}_temp"],
                    unit="°C",
                    icon="mdi:thermometer",
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                )
            )
    
    # Inlet Temperature Sensors
    sys_data = coordinator.data.get("system_data", {})
    sys_data_list = sys_data.get("SystemData", []) if sys_data else []

    for i in range(1, 5): # Check Loops 1-4
        # Ensure we have data for this index
        if i < len(sys_data_list):
            loop_data = sys_data_list[i]
            
            # Verify this is actually the correct circle_id (safety check)
            if loop_data.get("circle_id") == i:
                # Check if 'inlet_temp' exists in the JSON for this loop
                if "inlet_temp" in loop_data:
                    _LOGGER.info("Found inlet_temp for Loop %d, adding sensor.", i)
                    json_entities.append(
                        KronotermJsonSensor(
                            coordinator,
                            device_info,
                            f"loop_{i}_inlet_temp", # Unique suffix
                            f"loop_{i}_inlet_temperature", # Translation key
                            # Path: ["system_data", "SystemData", index(int), "inlet_temp"]
                            ["system_data", "SystemData", i, "inlet_temp"],
                            unit="°C",
                            icon="mdi:thermometer-chevron-down",
                            device_class=SensorDeviceClass.TEMPERATURE,
                            state_class=SensorStateClass.MEASUREMENT,
                        )
                    )

    # Energy sensors
    energy_sensors = [
        KronotermDailyEnergySensor(coordinator, "energy_heating", device_info, "CompHeating"),
        KronotermDailyEnergySensor(coordinator, "energy_dhw", device_info, "CompTapWater"),
        KronotermDailyEnergySensor(coordinator, "energy_circulation", device_info, "CPLoops"),
        KronotermDailyEnergySensor(coordinator, "energy_heater", device_info, "CPAddSource"),
        KronotermDailyEnergyCombinedSensor(
            coordinator,
            "energy_combined",
            device_info,
            ["CompHeating", "CompTapWater", "CPLoops", "CPAddSource"],
        ),
    ]
    for s in energy_sensors:
        s._attr_device_class = SensorDeviceClass.ENERGY
        s._attr_state_class = SensorStateClass.TOTAL_INCREASING

    all_entities = sensor_entities + enum_entities + json_entities + energy_sensors
    if all_entities:
        async_add_entities(all_entities)
        _LOGGER.info(
            "Added %d modbus, %d enum, %d JSON, %d energy sensors (total %d)",
            len(sensor_entities),
            len(enum_entities),
            len(json_entities),
            len(energy_sensors),
            len(all_entities),
        )
    else:
        _LOGGER.info("No sensors added.")
    return True

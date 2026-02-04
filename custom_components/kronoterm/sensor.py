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

# Import RegisterDefinition for type hints (may not exist if register_map not loaded)
try:
    from .register_map import RegisterDefinition
except ImportError:
    RegisterDefinition = None

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
    coordinator = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found.")
        return False

    device_info = coordinator.shared_device_info
    if not coordinator.data:
        _LOGGER.warning("No data from Kronoterm. Skipping sensors.")
        return False

    # Check if this is a Modbus coordinator with register map
    use_register_map = hasattr(coordinator, "register_map") and coordinator.register_map is not None
    
    if use_register_map:
        _LOGGER.info("Using JSON register map for Modbus TCP entities")
        return await _async_setup_modbus_entities(
            coordinator, device_info, async_add_entities
        )
    else:
        _LOGGER.info("Using hardcoded definitions for Cloud API entities")
        return await _async_setup_cloud_entities(
            coordinator, device_info, async_add_entities
        )


async def _async_setup_cloud_entities(
    coordinator: DataUpdateCoordinator,
    device_info: Dict[str, Any],
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Setup entities for Cloud API coordinator (original hardcoded approach)."""
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
            scale=1.0,  # Cloud API returns already-scaled decimal values (20.0, not 200)
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


async def _async_setup_modbus_entities(
    coordinator: DataUpdateCoordinator,
    device_info: Dict[str, Any],
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Setup entities for Modbus coordinator using JSON register map."""
    all_entities = []
    register_map = coordinator.register_map
    
    # Get all readable registers suitable for sensors
    sensors_to_create = register_map.get_sensors()
    
    _LOGGER.info("Found %d sensor registers in map", len(sensors_to_create))
    
    for reg_def in sensors_to_create:
        try:
            # Skip registers based on features not installed
            if not _should_create_sensor(coordinator, reg_def):
                continue
            
            # Create appropriate entity based on register type
            if reg_def.type == "Enum":
                # Enum sensor
                if not reg_def.values:
                    _LOGGER.debug("Skipping enum register %d with no value mappings", reg_def.address)
                    continue
                
                entity = KronotermEnumSensor(
                    coordinator=coordinator,
                    address=reg_def.address,
                    name=reg_def.name_en,
                    options=reg_def.values,
                    device_info=device_info,
                    icon=_get_icon_for_register(reg_def),
                )
            else:
                # Numeric sensor (Value, Value32, Status, Control)
                # Note: scale=1.0 because coordinator already applies scaling
                entity = KronotermModbusRegSensor(
                    coordinator=coordinator,
                    address=reg_def.address,
                    name=reg_def.name_en,
                    unit=reg_def.unit,
                    device_info=device_info,
                    scale=1.0,  # Coordinator already scaled the value
                    icon=_get_icon_for_register(reg_def),
                )
                
                # Apply device and state classes based on unit/type
                _apply_sensor_classes(entity, reg_def)
            
            # Mark diagnostic sensors
            if _is_diagnostic_sensor(reg_def):
                entity._attr_entity_category = EntityCategory.DIAGNOSTIC
            
            all_entities.append(entity)
            
        except Exception as e:
            _LOGGER.warning("Error creating sensor for register %d (%s): %s",
                          reg_def.address, reg_def.name, e)
            continue
    
    if all_entities:
        async_add_entities(all_entities)
        _LOGGER.info("Added %d Modbus sensors from register map", len(all_entities))
    else:
        _LOGGER.warning("No Modbus sensors created from register map!")
    
    return True


def _should_create_sensor(coordinator: DataUpdateCoordinator, reg_def: RegisterDefinition) -> bool:
    """Check if sensor should be created based on feature flags."""
    name_lower = reg_def.name_en.lower()
    
    # Skip ALL writable registers - they should be switch/number entities, not sensors
    if "Write" in reg_def.access:
        return False
    
    # Skip registers that have corresponding writable switch entities
    # Register 2000 (system_operation) is redundant - switch at 2012 shows state
    if reg_def.address == 2000:  # system_operation - use switch instead
        return False
    
    # Register 2003 (reserve_source) is redundant - switch at 2018 shows state
    if reg_def.address == 2003:  # reserve_source - use switch instead
        return False
    
    # Skip offset registers - they're handled by number entities only
    if "offset" in name_lower:
        return False
    
    # Skip pump status registers - they're handled by binary sensor entities only
    if "pump_status" in name_lower:
        return False
    
    # Skip pool sensors if not installed
    if "pool" in name_lower and not getattr(coordinator, "pool_installed", False):
        return False
    
    # Skip alternative source if not installed  
    if "alternative_source" in name_lower and not getattr(coordinator, "alt_source_installed", False):
        return False
    
    # Skip loop sensors based on installation
    if "loop_2" in name_lower and not getattr(coordinator, "loop2_installed", False):
        return False
    if "loop_3" in name_lower and not getattr(coordinator, "loop3_installed", False):
        return False
    if "loop_4" in name_lower and not getattr(coordinator, "loop4_installed", False):
        return False
    
    # Skip groundwater volume if value is 0 (not a groundwater heat pump)
    if "groundwater" in name_lower:
        # Check if the groundwater volume register (2349) exists and has non-zero value
        modbus_data = coordinator.data.get("main", {})
        for reg in modbus_data.get("ModbusReg", []):
            if reg.get("address") == 2349:
                value = reg.get("value", 0)
                if value == 0 or value == 0.0:
                    return False
                break
    
    # Skip thermostat sensors if thermostat temperature is 0 (no thermostat installed)
    # Map thermostat sensors to their temperature register addresses
    thermostat_checks = {
        "loop_1_thermostat": 2160,
        "loop_2_thermostat": 2161,
        "loop_3_thermostat": 2162,
        "loop_4_thermostat": 2163,
    }
    
    for prefix, temp_address in thermostat_checks.items():
        if prefix in name_lower:
            # Check if the thermostat temperature register is 0
            modbus_data = coordinator.data.get("main", {})
            for reg in modbus_data.get("ModbusReg", []):
                if reg.get("address") == temp_address:
                    value = reg.get("value", 0)
                    if value == 0 or value == 0.0:
                        return False
                    break
            break
    
    return True


def _is_diagnostic_sensor(reg_def: RegisterDefinition) -> bool:
    """Determine if sensor should be marked as diagnostic."""
    diagnostic_keywords = [
        "operating_hours",
        "activations",
        "alarm",
        "error",
        "napaka",
        "opozorilo",
        "cop",
        "scop",
    ]
    
    name_lower = reg_def.name_en.lower()
    return any(keyword in name_lower for keyword in diagnostic_keywords)


def _get_icon_for_register(reg_def: RegisterDefinition) -> str:
    """Get appropriate icon based on register name and type."""
    name_lower = reg_def.name_en.lower()
    
    # Temperature sensors
    if "temperature" in name_lower or reg_def.unit == "°C":
        if "outdoor" in name_lower or "outside" in name_lower or "external" in name_lower:
            return "mdi:thermometer"
        elif "water" in name_lower or "dhw" in name_lower:
            return "mdi:water-thermometer"
        elif "supply" in name_lower or "outlet" in name_lower:
            return "mdi:thermometer-chevron-up"
        elif "return" in name_lower or "inlet" in name_lower:
            return "mdi:thermometer-chevron-down"
        elif "thermostat" in name_lower:
            return "mdi:thermostat"
        else:
            return "mdi:thermometer"
    
    # Power/Energy
    if "power" in name_lower or "electrical" in name_lower or reg_def.unit == "W":
        return "mdi:lightning-bolt"
    if "energy" in name_lower or reg_def.unit == "kWh":
        return "mdi:meter-electric"
    
    # Pressure
    if "pressure" in name_lower or reg_def.unit == "bar":
        return "mdi:gauge"
    
    # Time/Hours
    if "hours" in name_lower or reg_def.unit == "h":
        return "mdi:timer-outline"
    
    # Pumps
    if "pump" in name_lower or "črpalka" in reg_def.name.lower():
        return "mdi:pump"
    
    # Compressor
    if "compressor" in name_lower or "kompresor" in reg_def.name.lower():
        return "mdi:engine"
    
    # Load/Percentage
    if "load" in name_lower or reg_def.unit == "%":
        return "mdi:gauge"
    
    # COP/SCOP
    if "cop" in name_lower or "scop" in name_lower:
        return "mdi:chart-line"
    
    # Status/Mode
    if reg_def.type in ("Status", "Enum"):
        return "mdi:information-outline"
    
    # Default
    return "mdi:flash"


def _apply_sensor_classes(entity: KronotermModbusRegSensor, reg_def: RegisterDefinition) -> None:
    """Apply device_class and state_class based on register properties."""
    # Temperature
    if reg_def.unit == "°C":
        entity._attr_device_class = SensorDeviceClass.TEMPERATURE
        entity._attr_state_class = SensorStateClass.MEASUREMENT
    
    # Energy
    elif reg_def.unit == "kWh":
        entity._attr_device_class = SensorDeviceClass.ENERGY
        entity._attr_state_class = SensorStateClass.TOTAL
    
    # Power
    elif reg_def.unit == "W":
        entity._attr_device_class = SensorDeviceClass.POWER
        entity._attr_state_class = SensorStateClass.MEASUREMENT
    
    # Pressure
    elif reg_def.unit == "bar":
        entity._attr_device_class = SensorDeviceClass.PRESSURE
        entity._attr_state_class = SensorStateClass.MEASUREMENT
    
    # Duration (hours)
    elif reg_def.unit == "h":
        entity._attr_device_class = SensorDeviceClass.DURATION
        entity._attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    # Percentage
    elif reg_def.unit == "%":
        entity._attr_state_class = SensorStateClass.MEASUREMENT

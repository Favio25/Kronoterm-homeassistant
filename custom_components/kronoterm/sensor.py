import logging
import re
from typing import Any, Dict, List, Optional, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from .energy import KronotermDailyEnergySensor, KronotermDailyEnergyCombinedSensor
from .const import DOMAIN

from .const import (
    DOMAIN,
    SENSOR_DEFINITIONS,
    ENUM_SENSOR_DEFINITIONS,
    POOL_TEMP_ADDRESS,
    ALT_SOURCE_TEMP_ADDRESS,
    COMPRESSOR_ACTIVATIONS_COOLING,
    HEATING_SOURCE_PRESSURE_SET,
    SOURCE_PRESSURE,
    diagnostic_sensor_addresses,
    diagnostic_enum_addresses
)

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# PART 1: ENTITY CLASSES
# -----------------------------------------------------------------------------

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
        self._name: str = name
        self._device_info: Dict[str, Any] = device_info
        self._unique_id: Optional[str] = None

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
                self._name,
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
        return bool(self.coordinator.last_update_success and self.coordinator.data)

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device info shared by Kronoterm entities."""
        return self._device_info

    @property
    def name(self) -> str:
        """Entity name."""
        return self._name


class KronotermModbusRegSensor(KronotermModbusBase, SensorEntity):
    """
    A sensor reading a numeric value (possibly scaled) from a Modbus register.
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
        """Return the sensor's native unit."""
        return self._unit

    def _process_value(self, raw_value: Any) -> Optional[float]:
        """Convert raw_value to float, remove non-numeric chars, apply scale, round to 2 decimals."""
        if isinstance(raw_value, str):
            raw_value = re.sub(r"[^\d\.]", "", raw_value)

        numeric_val = float(raw_value)
        if self._scale != 1:
            numeric_val *= self._scale
        return round(numeric_val, 2)

    @property
    def native_value(self) -> Optional[float]:
        """Return the processed numeric value."""
        return self._compute_value()


class KronotermBinarySensor(KronotermModbusBase, BinarySensorEntity):
    """
    A binary sensor reading an integer from Modbus, optionally checking a specific bit.
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
        """Return True if the register or bit indicates ON."""
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
    A sensor mapping a raw integer to a label via an options dictionary.
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
        """Return the mapped label if present, else None."""
        return self._options.get(raw_value)

    @property
    def native_value(self) -> Optional[str]:
        """Return the final label, or None if not found."""
        return self._compute_value()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    """
    Combined setup function that:
    1) Retrieves the single Kronoterm coordinator from hass.data[DOMAIN]["coordinator"]
    2) Creates the modbus-based, enum, and daily-energy sensors
    3) Adds them to Home Assistant
    """
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("No Kronoterm coordinator found. Cannot set up sensors.")
        return False

    device_info = coordinator.shared_device_info

    # Force a refresh so we have data
    await coordinator.async_config_entry_first_refresh()
    data = coordinator.data
    if not data:
        _LOGGER.warning("No data returned from Kronoterm. Skipping sensor setup.")
        return False

    main_data = data.get("main", {})
    modbus_list = main_data.get("ModbusReg", [])
    system_config = main_data.get("SystemConfiguration", {})

    # Build a dictionary for O(1) lookups:
    # { address_value: { "address": X, "value": Y, ...}, ... }
    modbus_dict = {entry["address"]: entry for entry in modbus_list if "address" in entry}

    # 1) Build the standard modbus sensors
    sensor_entities = []
    for (address, name, unit, icon, scale) in SENSOR_DEFINITIONS:
        sensor_ent = KronotermModbusRegSensor(
            coordinator=coordinator,
            address=address,
            name=name,
            unit=unit,
            device_info=device_info,
            scale=scale,
            icon=icon,
        )
        if address in diagnostic_sensor_addresses:
            sensor_ent._attr_entity_category = EntityCategory.DIAGNOSTIC
        # Additional customizations for specific sensors can be done here.

        # If it's the Electrical Energy sensor, treat it as a total-energy sensor
        if address == 2362:
            sensor_ent._attr_device_class = SensorDeviceClass.ENERGY
            sensor_ent._attr_state_class = SensorStateClass.TOTAL
        sensor_entities.append(sensor_ent)

    # 2) Build the enum sensors
    enum_sensor_entities = []
    for (address, name, options, icon) in ENUM_SENSOR_DEFINITIONS:
        enum_ent = KronotermEnumSensor(
            coordinator=coordinator,
            address=address,
            name=name,
            options=options,
            device_info=device_info,
            icon=icon,
        )
        if address in diagnostic_enum_addresses:
            enum_ent._attr_entity_category = EntityCategory.DIAGNOSTIC
        enum_sensor_entities.append(enum_ent)

    # Check optional flags in system_config for dynamic sensors
    pool_installed = bool(system_config.get("pool_installed", 0))
    alt_source_installed = bool(system_config.get("alts_installed", 0))
    cooling_installed = bool(system_config.get("cooling_installed", 0))
    heating_source_installed = True  # or read from system_config if needed

    # Helper to see if a register has a valid (non -60) temperature
    def is_valid_temp(reg_value: Any) -> bool:
        # For instance, Kronoterm uses "-60.0 °C" if sensor not installed
        return str(reg_value).strip().startswith("-60.0") is False

    # 3) Add optional/dynamic modbus sensors
    # Pool
    if pool_installed:
        reg_pool = modbus_dict.get(POOL_TEMP_ADDRESS)
        if reg_pool:
            raw_temp = reg_pool.get("value", "-60.0 °C")
            if is_valid_temp(raw_temp):
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=coordinator,
                        address=POOL_TEMP_ADDRESS,
                        name="Pool Temperature",
                        unit="°C",
                        device_info=device_info,
                        icon="mdi:pool",
                    )
                )
            else:
                _LOGGER.debug("Skipping pool sensor: value is %s", raw_temp)

    # Alternative Source
    if alt_source_installed:
        reg_alt = modbus_dict.get(ALT_SOURCE_TEMP_ADDRESS)
        if reg_alt:
            raw_temp = reg_alt.get("value", "-60.0 °C")
            if is_valid_temp(raw_temp):
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=coordinator,
                        address=ALT_SOURCE_TEMP_ADDRESS,
                        name="Alternative Source Temperature",
                        unit="°C",
                        device_info=device_info,
                        icon="mdi:fire",
                    )
                )

    # Cooling
    if cooling_installed:
        reg_cooling = modbus_dict.get(COMPRESSOR_ACTIVATIONS_COOLING)
        if reg_cooling:
            sensor_entities.append(
                KronotermModbusRegSensor(
                    coordinator=coordinator,
                    address=COMPRESSOR_ACTIVATIONS_COOLING,
                    name="Compressor Activations - Cooling",
                    unit="",
                    device_info=device_info,
                    icon="mdi:counter",
                )
            )

    # Heating Source Pressure
    if heating_source_installed:
        reg_2347 = modbus_dict.get(HEATING_SOURCE_PRESSURE_SET)
        if reg_2347:
            raw_val_2347 = str(reg_2347.get("value", "0")).lower()
            # If not zero, then add sensors for pressure set & source pressure
            if raw_val_2347 not in ("0", "0.0", "0 bar", "0.0 bar"):
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=coordinator,
                        address=HEATING_SOURCE_PRESSURE_SET,
                        name="Pressure Setting Heating Source",
                        unit="bar",
                        device_info=device_info,
                        icon="mdi:gauge",
                    )
                )
                # Add the source pressure sensor, if present
                if SOURCE_PRESSURE in modbus_dict:
                    sensor_entities.append(
                        KronotermModbusRegSensor(
                            coordinator=coordinator,
                            address=SOURCE_PRESSURE,
                            name="Source Pressure",
                            unit="bar",
                            device_info=device_info,
                            icon="mdi:gauge",
                        )
                    )

    # 4) Daily Energy sensors
    daily_energy_sensors = [
        KronotermDailyEnergySensor(
            coordinator=coordinator,
            name="Heating Energy",
            device_info=device_info,
            data_key="CompHeating",
        ),
        KronotermDailyEnergySensor(
            coordinator=coordinator,
            name="DHW Energy",
            device_info=device_info,
            data_key="CompTapWater",
        ),
        KronotermDailyEnergySensor(
            coordinator=coordinator,
            name="Pump Energy",
            device_info=device_info,
            data_key="CPLoops",
        ),
        KronotermDailyEnergySensor(
            coordinator=coordinator,
            name="Heater Energy",
            device_info=device_info,
            data_key="CPAddSource",
        ),
        KronotermDailyEnergyCombinedSensor(
            coordinator=coordinator,
            name="Combined Energy",
            device_info=device_info,
            data_keys=["CompHeating", "CompTapWater", "CPLoops", "CPAddSource"],
        ),
    ]

    # Set device class and state class for all energy sensors
    for sensor in daily_energy_sensors:
        sensor._attr_device_class = SensorDeviceClass.ENERGY
        sensor._attr_state_class = SensorStateClass.TOTAL_INCREASING

    all_entities = sensor_entities + enum_sensor_entities + daily_energy_sensors
    if all_entities:
        async_add_entities(all_entities, update_before_add=True)
        _LOGGER.info(
            "Added %d Modbus sensors, %d Enum sensors, and %d daily-energy sensors. Total: %d",
            len(sensor_entities),
            len(enum_sensor_entities),
            len(daily_energy_sensors),
            len(all_entities),
        )
    else:
        _LOGGER.info("No sensors to add.")
    return True
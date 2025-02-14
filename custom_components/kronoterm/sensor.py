import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
# Updated import to allow device_class and state_class for energy sensors:
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)

from .entities import KronotermModbusRegSensor, KronotermEnumSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Predefined "always-added" sensor definitions
SENSOR_DEFINITIONS = [
    # (address, name, unit, icon, scale)
    (2023, "Desired DHW Temperature", "°C", "mdi:water-boiler", 1),
    (2049, "Desired Loop 2 Temperature", "°C", "mdi:thermometer", 1),
    (2090, "Operating Hours Compressor Heating", "h", "mdi:timer-outline", 1),
    (2091, "Operating Hours Compressor DHW", "h", "mdi:timer-outline", 1),
    (2095, "Operating Hours Additional Source 1", "h", "mdi:timer-outline", 1),
    (2101, "Reservoir Temperature", "°C", "mdi:thermometer", 1),
    (2102, "DHW Temperature", "°C", "mdi:water-boiler", 1),
    (2103, "Outside Temperature", "°C", "mdi:weather-sunny", 1),
    (2104, "HP Outlet Temperature", "°C", "mdi:thermometer", 1),
    (2105, "Compressor Inlet Temperature", "°C", "mdi:thermometer", 1),
    (2106, "Compressor Outlet Temperature", "°C", "mdi:thermometer", 1),
    (2187, "Desired Loop 1 Temperature", "°C", "mdi:thermometer", 1),
    (2129, "Current Power Consumption", "W", "mdi:power-plug", 1),
    (2130, "Loop 1 Temperature", "°C", "mdi:thermometer", 0.1),
    (2110, "Loop 2 Temperature", "°C", "mdi:thermometer", 1),
    (2160, "Loop 1 Thermostat Temperature", "°C", "mdi:thermostat", 1),
    (2161, "Loop 2 Thermostat Temperature", "°C", "mdi:thermostat", 1),
    (2325, "Pressure Setting", "bar", "mdi:gauge", 1),
    (2326, "Heating System Pressure", "bar", "mdi:gauge", 1),
    (2327, "HP Load", "%", "mdi:engine", 1),
    (2329, "Current Heating/Cooling Capacity", "W", "mdi:lightning-bolt", 1),
    #(2347, "Pressure Setting Heating Source", "bar", "mdi:gauge", 1),
    # (2348, "Source Pressure", "bar", "mdi:gauge", 1),
    (2371, "COP Value", "", "mdi:chart-line", 0.01),
    (2372, "SCOP Value", "", "mdi:chart-line", 0.01),
    (2155, "Compressor Activations - Heating (24 h)", "", "mdi:counter", 1),
    (2157, "Boiler Activations (24 h)", "", "mdi:counter", 1),
    (2158, "Defrost Activations (24 h)", "", "mdi:snowflake-melt", 1),
    (2362, "Electrical Energy Heating + DHW", "kWh", "mdi:meter-electric", 1),
    (2364, "Heating Energy Heating + DHW", "kWh", "mdi:heat-wave", 1),
]

# Predefined "always-added" enum sensor definitions
ENUM_SENSOR_DEFINITIONS = [
    (
        2001,
        "Working Function",
        {
            0: "Heating",
            1: "DHW",
            2: "Cooling",
            3: "Pool Heating",
            4: "Thermal Disinfection",
            5: "Standby",
            7: "Remote Deactivation",
        },
        "mdi:heat-pump",
    ),
    (
        2006,
        "Error/Warning",
        {0: "No Error", 1: "Warning", 2: "Error"},
        "mdi:alert",
    ),
    (
        2007,
        "Operation Regime",
        {0: "Cooling", 1: "Heating", 2: "Heating and Cooling Off"},
        "mdi:heat-pump",
    ),
]


######################
# NEW ENERGY SENSORS #
######################

class KronotermDailyEnergySensor(CoordinatorEntity, SensorEntity):
    """
    A sensor that displays the *daily usage* from Kronoterm consumption data.
    The last array entry from e.g. data["trend_consumption"][data_key]
    is the current day's usage.
    """

    def __init__(
        self,
        coordinator,
        name,
        device_info,
        data_key,
    ):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"kronoterm_daily_{data_key}"
        self._device_info = device_info
        self._data_key = data_key

        # We'll assume it's kWh, but you can adjust:
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:flash"

        # Additional attributes for Energy usage in the Energy dashboard
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def device_info(self):
        return self._device_info

    @property
    def native_value(self):
        raw = self.coordinator.data
        if not raw:
            return None
        trend = raw.get("trend_consumption", {})
        arr = trend.get(self._data_key, [])
        if arr:
            value = arr[-1]
            if isinstance(value, (int, float)):
                return round(value, 3)
            return value
        return None


class KronotermDailyEnergyCombinedSensor(CoordinatorEntity, SensorEntity):
    """
    A sensor that sums multiple daily usage arrays (e.g. CompHeating, CompTapWater, CPLoops)
    and returns the combined value, rounded to 1 decimal.
    """

    def __init__(
        self,
        coordinator,
        name,
        device_info,
        data_keys,
    ):
        super().__init__(coordinator)
        self._attr_name = name

        # We'll join the keys for a unique_id
        joined_keys = "_".join(data_keys)
        self._attr_unique_id = f"kronoterm_daily_combined_{joined_keys}"
        self._device_info = device_info
        self._data_keys = data_keys

        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:counter"

        # Additional attributes for Energy usage
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def device_info(self):
        return self._device_info

    @property
    def native_value(self):
        raw = self.coordinator.data
        if not raw:
            return None
        trend = raw.get("trend_consumption", {})

        total = 0.0
        for key in self._data_keys:
            arr = trend.get(key, [])
            if arr:
                val = arr[-1]
                if isinstance(val, (int, float)):
                    total += val

        return round(total, 3)

#####################

# Addresses for potential dynamic sensors
POOL_TEMP_ADDRESS = 2109
ALT_SOURCE_TEMP_ADDRESS = 2107
COMPRESSOR_ACTIVATIONS_COOLING = 2156  # or whichever your device uses
HEATING_SOURCE_PRESSURE_SET = 2347
SOURCE_PRESSURE = 2348


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up Kronoterm sensors, both static and dynamic."""

    coordinator_wrapper = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator_wrapper:
        _LOGGER.error("No coordinator found. Cannot set up sensors.")
        return False

    main_coordinator = coordinator_wrapper.main_coordinator
    device_info = coordinator_wrapper.shared_device_info
    consumption_coordinator = coordinator_wrapper.consumption_coordinator

    # Ensure fresh data on main coordinator
    await main_coordinator.async_config_entry_first_refresh()
    data = main_coordinator.data
    if not data:
        _LOGGER.warning("No data returned from Kronoterm. Skipping sensor setup.")
        return False

    # --- Step A: Create the static (modbus) sensors ---
    sensor_entities = []
    for (address, name, unit, icon, scale) in SENSOR_DEFINITIONS:
        sensor_entities.append(
            KronotermModbusRegSensor(
                coordinator=main_coordinator,
                address=address,
                name=name,
                unit=unit,
                device_info=device_info,
                scale=scale,
                icon=icon,
            )
        )

    # --- Step B: Create the enum sensors ---
    enum_sensor_entities = []
    for (address, name, options, icon) in ENUM_SENSOR_DEFINITIONS:
        enum_sensor_entities.append(
            KronotermEnumSensor(
                coordinator=main_coordinator,
                address=address,
                name=name,
                options=options,
                device_info=device_info,
                icon=icon,
            )
        )

    modbus_list = data.get("ModbusReg", [])
    system_config = data.get("SystemConfiguration", {})

    # Booleans from system_config
    pool_installed = bool(system_config.get("pool_installed", 0))
    alt_source_installed = bool(system_config.get("alts_installed", 0))
    cooling_installed = bool(system_config.get("cooling_installed", 0))
    # If there's a different flag for "heating_source_installed", define it likewise
    heating_source_installed = True  # or check a specific key in `system_config`

    # --- Step C: Dynamic sensors ---

    # 1) Pool Temperature
    if pool_installed:
        reg_pool = next((r for r in modbus_list if r["address"] == POOL_TEMP_ADDRESS), None)
        if reg_pool:
            raw_temp = reg_pool.get("value", "-60.0 °C")
            if raw_temp != "-60.0 °C":
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=main_coordinator,
                        address=POOL_TEMP_ADDRESS,
                        name="Pool Temperature",
                        unit="°C",
                        device_info=device_info,
                        icon="mdi:pool",
                    )
                )
            else:
                _LOGGER.debug("Pool temp -60 => skipping pool sensor.")
        else:
            _LOGGER.debug("No pool register => skipping pool sensor.")
    else:
        _LOGGER.debug("pool_installed=0 => no pool sensor.")

    # 2) Alternative Source Temperature
    if alt_source_installed:
        reg_alt = next((r for r in modbus_list if r["address"] == ALT_SOURCE_TEMP_ADDRESS), None)
        if reg_alt:
            raw_temp = reg_alt.get("value", "-60.0 °C")
            if raw_temp != "-60.0 °C":
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=main_coordinator,
                        address=ALT_SOURCE_TEMP_ADDRESS,
                        name="Alternative Source Temperature",
                        unit="°C",
                        device_info=device_info,
                        icon="mdi:fire",
                    )
                )
    else:
        _LOGGER.debug("alts_installed=0 => no alt source sensor.")

    # 3) Compressor Cooling Activations
    if cooling_installed:
        reg_cooling = next((r for r in modbus_list if r["address"] == COMPRESSOR_ACTIVATIONS_COOLING), None)
        if reg_cooling:
            sensor_entities.append(
                KronotermModbusRegSensor(
                    coordinator=main_coordinator,
                    address=COMPRESSOR_ACTIVATIONS_COOLING,
                    name="Compressor Activations - Cooling",
                    unit="",
                    device_info=device_info,
                    icon="mdi:counter",
                )
            )
    else:
        _LOGGER.debug("cooling_installed=0 => no compressor cooling sensor.")

    # 4) Pressure Setting Heating Source + Source Pressure
    if heating_source_installed:
        reg_2347 = next((r for r in modbus_list if r["address"] == HEATING_SOURCE_PRESSURE_SET), None)
        if reg_2347:
            raw_val_2347 = str(reg_2347.get("value", "0")).lower()
            if raw_val_2347 not in ("0", "0.0", "0 bar", "0.0 bar"):
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=main_coordinator,
                        address=HEATING_SOURCE_PRESSURE_SET,
                        name="Pressure Setting Heating Source",
                        unit="bar",
                        device_info=device_info,
                        icon="mdi:gauge",
                    )
                )
                sensor_entities.append(
                    KronotermModbusRegSensor(
                        coordinator=main_coordinator,
                        address=SOURCE_PRESSURE,
                        name="Source Pressure",
                        unit="bar",
                        device_info=device_info,
                        icon="mdi:gauge",
                    )
                )
            else:
                _LOGGER.debug("Heating source reg 2347 = %s => skip 2347 & 2348", raw_val_2347)
        else:
            _LOGGER.debug("No reg 2347 => skip heating source sensors.")
    else:
        _LOGGER.debug("heating_source_installed=0 => skip 2347 & 2348")

    # --- Step D: Energy sensors from consumption coordinator ---
    # We'll define daily usage sensors for e.g. CompHeating, CompTapWater, CPLoops, etc.

    # Make sure the consumption coordinator has data
    await consumption_coordinator.async_config_entry_first_refresh()
    consumption_data = consumption_coordinator.data
    if not consumption_data:
        _LOGGER.warning("No consumption data returned. Energy sensors might be None.")

    # 1) Individual sensors
    energy_sensors = [
        KronotermDailyEnergySensor(
            coordinator=consumption_coordinator,
            name="Daily Heating Energy",
            device_info=device_info,
            data_key="CompHeating",
        ),
        KronotermDailyEnergySensor(
            coordinator=consumption_coordinator,
            name="Daily DHW Energy",
            device_info=device_info,
            data_key="CompTapWater",
        ),
        KronotermDailyEnergySensor(
            coordinator=consumption_coordinator,
            name="Daily Pumps Energy",
            device_info=device_info,
            data_key="CPLoops",
        ),
        KronotermDailyEnergySensor(
            coordinator=consumption_coordinator,
            name="Daily Heater Energy",
            device_info=device_info,
            data_key="CPAddSource",
    ),
    ]

    # 2) Combined sensor that sums these three arrays and rounds to 1 decimal
    combined_sensor = KronotermDailyEnergyCombinedSensor(
        coordinator=consumption_coordinator,
        name="Daily Combined Energy",
        device_info=device_info,
        data_keys=["CompHeating", "CompTapWater", "CPLoops", "CPAddSource"]
    )
    energy_sensors.append(combined_sensor)

    # --- Combine everything and add them ---
    all_entities = sensor_entities + enum_sensor_entities + energy_sensors
    if all_entities:
        async_add_entities(all_entities)
        _LOGGER.info(
            "Added %d sensors + %d enum sensors + %d energy sensors. Total: %d",
            len(sensor_entities),
            len(enum_sensor_entities),
            len(energy_sensors),
            len(all_entities),
        )
    else:
        _LOGGER.info("No sensors to add.")
    return True

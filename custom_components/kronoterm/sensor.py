import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .entities import KronotermModbusRegSensor, KronotermEnumSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up the Kronoterm sensor platform."""
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("No data found in hass.data for domain %s", DOMAIN)
        return False

    coordinator = data.get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data for domain %s", DOMAIN)
        return False

    shared_device_info = coordinator.shared_device_info
    main_coordinator = coordinator.main_coordinator

    # Define Modbus register sensors
    sensor_entities = [
        KronotermModbusRegSensor(
            main_coordinator, 2023, "Desired DHW Temperature", "°C",
            shared_device_info, icon="mdi:water-boiler"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2051, "Desired loop 2 temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2090, "Operating Hours Compressor Heating", "h",
            shared_device_info, icon="mdi:timer-outline"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2091, "Operating Hours Compressor DHW", "h",
            shared_device_info, icon="mdi:timer-outline"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2095, "Operating Hours Additional Source 1", "h",
            shared_device_info, icon="mdi:timer-outline"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2101, "Reservoir Temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2102, "DHW Temperature", "°C",
            shared_device_info, icon="mdi:water-boiler"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2103, "Outside Temperature", "°C",
            shared_device_info, icon="mdi:weather-sunny"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2104, "HP Outlet Temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2105, "Compressor Inlet Temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2106, "Compressor Outlet Temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2107, "Alternative Source Temperature", "°C",
            shared_device_info, icon="mdi:fire"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2109, "Pool Temperature", "°C",
            shared_device_info, icon="mdi:pool"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2187, "Desired loop 1 temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2129, "Current Power Consumption", "W",
            shared_device_info, icon="mdi:power-plug"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2130, "Loop 1 Temperature", "°C",
            shared_device_info, icon="mdi:thermometer", scale=0.1
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2110, "Loop 2 Temperature", "°C",
            shared_device_info, icon="mdi:thermometer"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2160, "Loop 1 Thermostat Temperature", "°C",
            shared_device_info, icon="mdi:thermostat"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2161, "Loop 2 Thermostat Temperature", "°C",
            shared_device_info, icon="mdi:thermostat"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2325, "Pressure Setting", "bar",
            shared_device_info, icon="mdi:gauge"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2326, "Heating System Pressure", "bar",
            shared_device_info, icon="mdi:gauge"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2327, "HP Load", " %",
            shared_device_info, icon="mdi:engine"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2329, "Current Heating/Cooling Capacity", "W",
            shared_device_info, icon="mdi:lightning-bolt"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2347, "Pressure Setting Heating Source", "bar",
            shared_device_info, icon="mdi:gauge"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2348, "Source Pressure", "bar",
            shared_device_info, icon="mdi:gauge"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2371, "COP Value", "",
            shared_device_info, icon="mdi:chart-line", scale=0.01
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2372, "SCOP Value", "",
            shared_device_info, icon="mdi:chart-line", scale=0.01
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2155, "Compressor Activations - Heating (24 h)", "",
            shared_device_info, icon="mdi:counter"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2156, "Compressor Activations - Cooling (24 h)", "",
            shared_device_info, icon="mdi:counter"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2157, "Boiler Activations (24 h)", "",
            shared_device_info, icon="mdi:counter"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2158, "Defrost Activations (24 h)", "",
            shared_device_info, icon="mdi:snowflake-melt"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2362, "Electrical Energy Heating + DHW", "kWh",
            shared_device_info, icon="mdi:meter-electric"
        ),
        KronotermModbusRegSensor(
            main_coordinator, 2364, "Heating Energy Heating + DHW", "kWh",
            shared_device_info, icon="mdi:heat-wave"
        ),
    ]

    # Define enumeration sensors
    enum_sensor_entities = [
        KronotermEnumSensor(
            main_coordinator, 2001, "Working Function",
            {
                0: "Heating", 1: "DHW", 2: "Cooling", 3: "Pool Heating",
                4: "Thermal Disinfection", 5: "Standby", 7: "Remote Deactivation"
            },
            shared_device_info, icon="mdi:heat-pump"
        ),
        KronotermEnumSensor(
            main_coordinator, 2006, "Error/Warning",
            {0: "No Error", 1: "Warning", 2: "Error"},
            shared_device_info, icon="mdi:alert"
        ),
        KronotermEnumSensor(
            main_coordinator, 2007, "Operation Regime",
            {0: "Cooling", 1: "Heating", 2: "Heating and Cooling Off"},
            shared_device_info, icon="mdi:heat-pump"
        ),
    ]

    # Combine both sensor groups
    entities = sensor_entities + enum_sensor_entities

    async_add_entities(entities)
    return True

from datetime import timedelta
import logging
import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

API_URL_MAIN = "https://cloud.kronoterm.com/jsoncgi.php?TopPage=5&Subpage=3"
API_URL_INFO = "https://cloud.kronoterm.com/jsoncgi.php?TopPage=1&Subpage=1"

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = config_entry.data

    async def async_update_main_data():
        """Fetch main data from the Kronoterm API."""
        _LOGGER.debug("Starting main data update...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    API_URL_MAIN,
                    auth=aiohttp.BasicAuth(config["username"], config["password"])
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"HTTP error: {response.status}")
                    data = await response.json()
                    _LOGGER.debug(f"Main data fetched successfully: {data}")
                    return data
        except Exception as e:
            _LOGGER.error(f"Error communicating with main API: {e}")
            raise UpdateFailed(f"Error communicating with main API: {e}")

    async def async_update_info_data():
        """Fetch info data from the Kronoterm API."""
        _LOGGER.debug("Starting info data update...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    API_URL_INFO,
                    auth=aiohttp.BasicAuth(config["username"], config["password"])
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"HTTP error: {response.status}")
                    data = await response.json()
                    _LOGGER.debug(f"Info data fetched successfully: {data}")
                    return data
        except Exception as e:
            _LOGGER.error(f"Error communicating with info API: {e}")
            raise UpdateFailed(f"Error communicating with info API: {e}")


    update_interval = timedelta(seconds=config.get("scan_interval", 300))  # Default to 60 seconds

    main_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="kronoterm_main",
        update_method=async_update_main_data,
        update_interval=update_interval,
    )

    info_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="kronoterm_info",
        update_method=async_update_info_data,
        update_interval=timedelta(hours=24),  # Update info data less frequently
    )

    try:
        await main_coordinator.async_config_entry_first_refresh()
        await info_coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.error("Error fetching initial data: %s", err)
        raise ConfigEntryNotReady

    # Prepare shared device info
    info_data = info_coordinator.data.get("InfoData", {})
    shared_device_info = {
        "identifiers": {(DOMAIN, info_data.get("device_id", "kronoterm_heat_pump"))},
        "name": "Kronoterm Heat Pump",
        "manufacturer": "Kronoterm",
        "model": info_data.get("pumpModel", "Unknown Model"),
        "sw_version": info_data.get("firmware", "Unknown Firmware"),
    }

    # Define sensors and binary sensors directly with corrected attributes
    entities = [
        KronotermModbusRegSensor(main_coordinator, 2023, "Desired DHW Temperature", "", shared_device_info, icon="mdi:water-boiler"),
        KronotermModbusRegSensor(main_coordinator, 2090, "Operating Hours Compressor Heating", "", shared_device_info, icon="mdi:timer-outline"),
        KronotermModbusRegSensor(main_coordinator, 2091, "Operating Hours Compressor DHW", "", shared_device_info, icon="mdi:timer-outline"),
        KronotermModbusRegSensor(main_coordinator, 2095, "Operating Hours Additional Source 1", "", shared_device_info, icon="mdi:timer-outline"),
        KronotermModbusRegSensor(main_coordinator, 2101, "Reservoir Temperature", "", shared_device_info, icon="mdi:thermometer"),
        KronotermModbusRegSensor(main_coordinator, 2102, "DHW Temperature", "", shared_device_info, icon="mdi:water-boiler"),
        KronotermModbusRegSensor(main_coordinator, 2103, "Outside Temperature", "", shared_device_info, icon="mdi:weather-sunny"),
        KronotermModbusRegSensor(main_coordinator, 2104, "HP Outlet Temperature", "", shared_device_info, icon="mdi:thermometer"),
        KronotermModbusRegSensor(main_coordinator, 2105, "Compressor inlet temperature", "", shared_device_info, icon="mdi:thermometer"),
        KronotermModbusRegSensor(main_coordinator, 2106, "Compressor outlet temperature", "", shared_device_info, icon="mdi:thermometer"),
        KronotermModbusRegSensor(main_coordinator, 2107, "Alternative source temperature", "", shared_device_info, icon="mdi:fire"),
        KronotermModbusRegSensor(main_coordinator, 2109, "Pool temperature", "", shared_device_info, icon="mdi:pool"),
        KronotermModbusRegSensor(main_coordinator, 2129, "Current Power Consumption", "", shared_device_info, icon="mdi:power-plug"),
        KronotermModbusRegSensor(main_coordinator, 2130, "Loop 1 Temperature", "°C", shared_device_info, icon="mdi:thermometer", scale=0.1),
        KronotermModbusRegSensor(main_coordinator, 2110, "Loop 2 Temperature", "", shared_device_info, icon="mdi:thermometer"),
        KronotermModbusRegSensor(main_coordinator, 2160, "Loop 1 Thermostat Temperature", "", shared_device_info, icon="mdi:thermostat"),
        KronotermModbusRegSensor(main_coordinator, 2161, "Loop 2 Thermostat Temperature", "", shared_device_info, icon="mdi:thermostat"),
        KronotermModbusRegSensor(main_coordinator, 2325, "Pressure Setting", "", shared_device_info, icon="mdi:gauge"),
        KronotermModbusRegSensor(main_coordinator, 2326, "Heating System Pressure", "", shared_device_info, icon="mdi:gauge"),
        KronotermModbusRegSensor(main_coordinator, 2327, "HP Load", "%", shared_device_info, icon="mdi:engine"),
        KronotermModbusRegSensor(main_coordinator, 2329, "Current heating/cooling capacity", "", shared_device_info, icon="mdi:lightning-bolt"),
        KronotermModbusRegSensor(main_coordinator, 2347, "Pressure Setting heating source", "", shared_device_info, icon="mdi:gauge"),
        KronotermModbusRegSensor(main_coordinator, 2348, "Source Pressure", "", shared_device_info, icon="mdi:gauge"),
        KronotermModbusRegSensor(main_coordinator, 2371, "COP Value", "", shared_device_info, icon="mdi:chart-line", scale=0.01),
        KronotermModbusRegSensor(main_coordinator, 2372, "SCOP Value", "", shared_device_info, icon="mdi:chart-line", scale=0.01),
        KronotermModbusRegSensor(main_coordinator, 2155, "Compressor activations - heating (24 h)", "", shared_device_info, icon="mdi:counter"),
        KronotermModbusRegSensor(main_coordinator, 2156, "Compressor activations - cooling (24 h)", "", shared_device_info, icon="mdi:counter"),
        KronotermModbusRegSensor(main_coordinator, 2157, "Boiler activations (24 h)", "", shared_device_info, icon="mdi:counter"),
        KronotermModbusRegSensor(main_coordinator, 2158, "Defrost Activations (24 h)", "", shared_device_info, icon="mdi:snowflake-melt"),
        KronotermModbusRegSensor(main_coordinator, 2362, "Electrical Energy Heating + DHW", "kWh", shared_device_info, icon="mdi:meter-electric"),
        KronotermModbusRegSensor(main_coordinator, 2364, "Heating Energy Heating + DHW ", "kWh", shared_device_info, icon="mdi:heat-wave"),
        KronotermBinarySensor(main_coordinator, 2000, "System Operation", shared_device_info, icon="mdi:power"),
        KronotermBinarySensor(main_coordinator, 2045, "Loop 1 Circulation", shared_device_info, icon="mdi:pump"),
        KronotermBinarySensor(main_coordinator, 2055, "Loop 2 Circulation", shared_device_info, icon="mdi:pump"),
        KronotermBinarySensor(main_coordinator, 2002, "Aditional source", shared_device_info, bit=0, icon="mdi:fire"),
        KronotermBinarySensor(main_coordinator, 2028, "DHW Circulation", shared_device_info, bit=0, icon="mdi:pump"),
        KronotermEnumSensor(main_coordinator, 2001, "Working Function", {0: "heating", 1: "DHW", 2: "cooling", 3: "pool heating", 4: "thermal disinfection", 5: "standby", 7: "remote deactivation"}, shared_device_info, icon="mdi:heat-pump"),
        KronotermEnumSensor(main_coordinator, 2006, "Error/Warning", {0: "no error", 1: "opozorilo", 2: "error"}, shared_device_info, icon="mdi:alert"),
        KronotermEnumSensor(main_coordinator, 2007, "Operation Regime", {0: "cooling", 1: "heating", 2: "heating and cooling off"}, shared_device_info, icon="mdi:heat-pump"),
        KronotermEnumSensor(main_coordinator, 2044, "Loop 1 Status", {0: "off", 1: "normal", 2: "ECO", 3: "COM"}, shared_device_info, icon="mdi:radiator"),
    ]

    async_add_entities(entities)

class KronotermModbusRegSensor(SensorEntity):
    def __init__(self, coordinator, address, name, unit, device_info, scale=1, icon=None):
        self._coordinator = coordinator
        self._address = address
        self._name = name
        self._unit = unit
        self._device_info = device_info
        self._scale = scale
        self._icon = icon
        self._unique_id = f"{DOMAIN}_modbus_{address}"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        # Access the value by address from ModbusReg and apply scaling
        modbus_regs = self._coordinator.data.get("ModbusReg", [])
        raw_value = next((reg["value"] for reg in modbus_regs if reg.get("address") == self._address), None)
        if raw_value is not None:
            try:
                if self._scale != 1:
                    scaled_value = float(raw_value) * self._scale
                    return round(scaled_value, 2) if isinstance(scaled_value, float) else scaled_value
                return raw_value
            except (ValueError, TypeError):
                return "unknown"
        return "unknown"

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        await self._coordinator.async_request_refresh()

    @property
    def available(self):
        return self._coordinator.last_update_success

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return self._device_info

class KronotermBinarySensor(BinarySensorEntity):
    def __init__(self, coordinator, address, name, device_info, bit=None, icon=None):
        self._coordinator = coordinator
        self._address = address
        self._name = name
        self._device_info = device_info
        self._bit = bit
        self._icon = icon
        self._unique_id = f"{DOMAIN}_binary_{address}_{bit}" if bit is not None else f"{DOMAIN}_binary_{address}"

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        # Access the value by address from ModbusReg and check bit if applicable
        modbus_regs = self._coordinator.data.get("ModbusReg", [])
        raw_value = next((reg["value"] for reg in modbus_regs if reg.get("address") == self._address), None)
        if raw_value is not None:
            try:
                if self._bit is not None:
                    return bool(raw_value & (1 << self._bit))
                return bool(raw_value)
            except (ValueError, TypeError):
                return False
        return False

    @property
    def icon(self):
        return self._icon

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        await self._coordinator.async_request_refresh()

    @property
    def available(self):
        return self._coordinator.last_update_success

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return self._device_info
        
class KronotermEnumSensor(SensorEntity):
    def __init__(self, coordinator, address, name, options, device_info, icon=None):
        self._coordinator = coordinator
        self._address = address
        self._name = name
        self._options = options
        self._device_info = device_info
        self._icon = icon
        self._unique_id = f"{DOMAIN}_enum_{address}"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        modbus_regs = self._coordinator.data.get("ModbusReg", [])
        raw_value = next((reg["value"] for reg in modbus_regs if reg.get("address") == self._address), None)
        return self._options.get(raw_value, "unknown")

    @property
    def icon(self):
        return self._icon

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        await self._coordinator.async_request_refresh()

    @property
    def available(self):
        return self._coordinator.last_update_success

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
        return self._device_info

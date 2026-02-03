"""
Kronoterm Modbus TCP Coordinator.

Handles communication with Kronoterm heat pump via Modbus TCP.
Alternative to cloud API for local control.
"""

import logging
import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .modbus_registers import (
    Register,
    RegisterType,
    scale_value,
    format_enum,
    read_bit,
    ALL_REGISTERS,
    DEVICE_ID,
    FIRMWARE_VERSION,
    OUTDOOR_TEMP,
    LOOP1_CURRENT_TEMP,
    LOOP1_SETPOINT,
    DHW_SETPOINT,
    WORKING_FUNCTION,
    HP_LOAD,
    CURRENT_POWER,
    SYSTEM_PRESSURE,
    COP,
)

_LOGGER = logging.getLogger(__name__)

# Error values that indicate sensor not connected
# Values above 64000 are typically error codes in Kronoterm
# HP Outlet tends to return values in 65490-65530 range when sensor not connected
ERROR_VALUES = [64936, 64937, 65535, 65526, 65517, 65497, 65499, 65493]

# Modbus unit ID (slave address)
DEFAULT_UNIT_ID = 20


class ModbusCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from Kronoterm via Modbus TCP."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
    ):
        """Initialize the Modbus coordinator."""
        self.hass = hass
        self.config_entry = config_entry

        # Extract Modbus connection details
        self.host = config_entry.data.get(CONF_HOST)
        self.port = config_entry.data.get(CONF_PORT, 502)
        self.unit_id = config_entry.data.get("unit_id", DEFAULT_UNIT_ID)
        self.model = config_entry.data.get("model", "unknown")

        # Modbus client
        self.client: Optional[AsyncModbusTcpClient] = None
        self._connected = False

        # Shared device info
        self.shared_device_info: Dict[str, Any] = {}
        
        # Feature flags (to match cloud coordinator interface)
        self.loop1_installed = True  # Assume installed
        self.loop2_installed = False
        self.loop3_installed = False
        self.loop4_installed = False
        self.dhw_installed = True
        self.tap_water_installed = True  # Alias for DHW
        self.additional_source_installed = False
        self.alt_source_installed = False  # Alias for additional_source
        self.reservoir_installed = False
        self.pool_installed = False

        # Scan interval
        scan_interval = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        scan_interval = max(scan_interval, 1)
        _LOGGER.info("Modbus coordinator update interval set to %d minutes", scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name="kronoterm_modbus_coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=scan_interval),
        )

    async def async_initialize(self) -> None:
        """Initialize Modbus connection and fetch device info."""
        _LOGGER.warning("🔥 Initializing Modbus connection to %s:%s (unit_id=%s)", 
                       self.host, self.port, self.unit_id)
        
        # Create Modbus client
        self.client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
        )
        
        # Try to connect
        try:
            connected = await self.client.connect()
            if not connected:
                raise UpdateFailed(f"Failed to connect to Modbus device at {self.host}:{self.port}")
            
            self._connected = True
            _LOGGER.info("Successfully connected to Modbus device")
            
            # Fetch device info
            await self._fetch_device_info()
            
            # Do initial data fetch using proper coordinator method
            # This will populate self.data properly
            await self.async_config_entry_first_refresh()
            _LOGGER.warning("🔥 Initialization complete! Data has %d entries", len(self.data) if self.data else 0)
            
        except Exception as err:
            _LOGGER.error("Error during Modbus initialization: %s", err)
            self._connected = False
            raise UpdateFailed(f"Modbus initialization failed: {err}")

    async def _fetch_device_info(self) -> None:
        """Fetch device identification from Modbus."""
        try:
            # Read device ID
            device_id_raw = await self._read_register(DEVICE_ID)
            device_id = f"kronoterm_{device_id_raw:04X}" if device_id_raw else "kronoterm"
            
            # Read firmware version
            firmware_raw = await self._read_register(FIRMWARE_VERSION)
            firmware = f"{firmware_raw}" if firmware_raw else "unknown"
            
            # Build device info
            model_name = self._format_model_name()
            
            self.shared_device_info = {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Kronoterm {model_name}",
                "manufacturer": "Kronoterm",
                "model": model_name,
                "sw_version": firmware,
                "configuration_url": f"http://{self.host}",
            }
            
            _LOGGER.info("Device info: %s", self.shared_device_info)
            
        except Exception as err:
            _LOGGER.warning("Could not fetch device info: %s", err)
            # Use fallback device info
            self.shared_device_info = {
                "identifiers": {(DOMAIN, f"kronoterm_{self.host}")},
                "name": "Kronoterm Heat Pump",
                "manufacturer": "Kronoterm",
                "model": self._format_model_name(),
            }

    def _format_model_name(self) -> str:
        """Format model name for display."""
        model_map = {
            "adapt_0312": "ADAPT 0312",
            "adapt_0416": "ADAPT 0416",
            "adapt_0724": "ADAPT 0724",
            "unknown": "Heat Pump",
        }
        return model_map.get(self.model, "Heat Pump")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Modbus device."""
        _LOGGER.warning("🔥 _async_update_data called, _connected=%s", self._connected)
        
        if not self._connected:
            raise UpdateFailed("Modbus client not connected")

        try:
            data = {}
            _LOGGER.warning("🔥 Reading %d registers...", len(ALL_REGISTERS))
            
            # Read all registers
            for register in ALL_REGISTERS:
                try:
                    raw_value = await self._read_register(register)
                    
                    if raw_value is None:
                        continue
                    
                    # Process based on register type
                    if register.reg_type == RegisterType.BITS:
                        # Bit-masked value
                        value = read_bit(raw_value, register.bit)
                    elif register.reg_type == RegisterType.BINARY:
                        # Binary sensor
                        value = bool(raw_value)
                    elif register.reg_type == RegisterType.ENUM:
                        # For ENUM, store RAW value - the entity will do the mapping
                        value = raw_value
                    else:
                        # Scaled numeric value
                        value = scale_value(register, raw_value)
                        if value is None:
                            continue
                    
                    # Store in data dict using register address as key
                    data[register.address] = {
                        "value": value,
                        "raw": raw_value,
                        "name": register.name,
                        "unit": register.unit if hasattr(register, 'unit') else None,
                    }
                    
                except Exception as err:
                    _LOGGER.debug("Error reading register %s (%d): %s", 
                                 register.name, register.address, err)
                    continue
            
            if not data:
                _LOGGER.error("🔥 NO DATA COLLECTED! All register reads failed!")
                raise UpdateFailed("No data received from Modbus device")
            
            # Update feature flags based on data
            self._update_feature_flags(data)
            
            # Format data for entity compatibility: entities expect data["main"]["ModbusReg"]
            # Convert from {addr: {value, raw, name}} to the expected format
            modbus_reg_list = []
            for address, info in data.items():
                modbus_reg_list.append({
                    "address": address,
                    "value": info["value"],
                    "raw": info["raw"],
                    "name": info["name"],
                    "unit": info.get("unit"),
                })
            
            formatted_data = {
                "main": {
                    "ModbusReg": modbus_reg_list
                }
            }
            
            _LOGGER.warning("🔥 Successfully read %d registers from Modbus!", len(modbus_reg_list))
            return formatted_data
            
        except ModbusException as err:
            _LOGGER.error("Modbus communication error: %s", err)
            raise UpdateFailed(f"Modbus error: {err}")
        except Exception as err:
            _LOGGER.error("Unexpected error during Modbus update: %s", err)
            raise UpdateFailed(f"Update failed: {err}")

    async def _read_register(self, register: Register) -> Optional[int]:
        """Read a single register from Modbus device."""
        try:
            result = await self.client.read_holding_registers(
                register.address, count=1, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.warning("Error reading register %d (%s): %s", 
                              register.address, register.name, result)
                return None
            
            value = result.registers[0]
            
            # Check for error values
            # Kronoterm uses values >= 64000 to indicate sensor errors/not connected
            if value >= 64000 or value in ERROR_VALUES:
                _LOGGER.debug("Register %d returned error value %d", register.address, value)
                return None
            
            return value
            
        except Exception as err:
            _LOGGER.warning("Exception reading register %d (%s): %s", 
                          register.address, register.name, err)
            return None

    async def write_register(self, register: Register, value: int) -> bool:
        """Write a value to a Modbus register."""
        if not self._connected:
            _LOGGER.error("Cannot write register: Modbus not connected")
            return False
        
        try:
            _LOGGER.info("Writing value %d to register %d (%s)", 
                        value, register.address, register.name)
            
            result = await self.client.write_register(
                register.address, value=value, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.error("Error writing register %d: %s", register.address, result)
                return False
            
            # Request immediate refresh
            await self.async_request_refresh()
            
            return True
            
        except Exception as err:
            _LOGGER.error("Exception writing register %d: %s", register.address, err)
            return False

    def _update_feature_flags(self, data: Dict[str, Any]) -> None:
        """Update feature flags based on current data."""
        # Check if Loop 2 is installed (non-zero setpoint or current temp)
        loop2_setpoint = data.get(2049, {}).get("value", 0)
        loop2_current = data.get(2110, {}).get("value")
        self.loop2_installed = (loop2_setpoint and loop2_setpoint > 0.5) or bool(loop2_current)
        
        # Check if additional source is installed
        add_source = data.get(2002, {}).get("raw", 0)
        self.additional_source_installed = bool(add_source)

    def get_register_value(self, register: Register) -> Optional[Any]:
        """Get current value of a register from cached data."""
        if not self.data:
            return None
        
        # Data is now in format: {"main": {"ModbusReg": [...]}}
        modbus_reg_list = self.data.get("main", {}).get("ModbusReg", [])
        for reg in modbus_reg_list:
            if reg.get("address") == register.address:
                return reg.get("value")
        
        return None
        return None

    # =================================================================
    # HIGH-LEVEL WRITE METHODS
    # (Match Cloud API coordinator interface for entity compatibility)
    # =================================================================

    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        """Set temperature setpoint for a loop or DHW based on page."""
        # Map Cloud API "page" to Modbus registers
        page_to_register = {
            5: 2187,  # Loop 1 setpoint
            6: 2049,  # Loop 2 setpoint
            9: 2023,  # DHW setpoint
        }
        
        register_address = page_to_register.get(page)
        if not register_address:
            _LOGGER.error("Unknown page %d for temperature setpoint", page)
            return False
        
        # Convert temperature to Modbus format (× 10)
        modbus_value = int(round(new_temp * 10))
        
        _LOGGER.info("Setting temperature for page %d to %.1f°C (modbus value: %d)", 
                    page, new_temp, modbus_value)
        
        # Create temporary register object for write_register method
        from .modbus_registers import Register, RegisterType
        temp_register = Register(
            address=register_address,
            name=f"Setpoint_Page_{page}",
            reg_type=RegisterType.TEMP
        )
        
        return await self.write_register(temp_register, modbus_value)

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """Set temperature offset (eco/comfort) for a loop or DHW."""
        # Map page + param_name to Modbus register
        offset_map = {
            # (page, param_name): register_address
            (5, "circle_eco_offset"): 2047,      # Loop 1 eco
            (5, "circle_comfort_offset"): 2048,  # Loop 1 comfort
            (6, "circle_eco_offset"): 2057,      # Loop 2 eco
            (6, "circle_comfort_offset"): 2058,  # Loop 2 comfort
            (7, "circle_eco_offset"): 2067,      # Loop 3 eco
            (7, "circle_comfort_offset"): 2068,  # Loop 3 comfort
            (8, "circle_eco_offset"): 2077,      # Loop 4 eco
            (8, "circle_comfort_offset"): 2078,  # Loop 4 comfort
            (9, "circle_eco_offset"): 2030,      # DHW eco
            (9, "circle_comfort_offset"): 2031,  # DHW comfort
        }
        
        register_address = offset_map.get((page, param_name))
        if not register_address:
            _LOGGER.error("Unknown offset: page=%d, param=%s", page, param_name)
            return False
        
        # Convert offset to Modbus format (× 10)
        modbus_value = int(round(new_value * 10))
        
        _LOGGER.info("Setting offset for page %d/%s to %.1f°C (modbus value: %d)",
                    page, param_name, new_value, modbus_value)
        
        from .modbus_registers import Register, RegisterType
        temp_register = Register(
            address=register_address,
            name=f"Offset_{page}_{param_name}",
            reg_type=RegisterType.TEMP
        )
        
        return await self.write_register(temp_register, modbus_value)

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """Enable/disable heat pump system operation (register 2002 bit 0)."""
        # NOTE: Register 2002 is a bit-masked register
        # We need to read current value, modify bit 0, and write back
        # For now, simple implementation: write 1 or 0
        # TODO: Read-modify-write if other bits are important
        
        value = 1 if turn_on else 0
        _LOGGER.info("Setting heat pump state to %s (value: %d)", "ON" if turn_on else "OFF", value)
        
        from .modbus_registers import Register, RegisterType
        system_register = Register(
            address=2002,
            name="System_Operation",
            reg_type=RegisterType.BINARY
        )
        
        return await self.write_register(system_register, value)

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        """Set loop operation mode (off/normal/eco/comfort) based on page."""
        # Map page to loop mode register
        page_to_register = {
            5: 2042,  # Loop 1
            6: 2052,  # Loop 2
            7: 2062,  # Loop 3
            8: 2072,  # Loop 4
            9: 2026,  # DHW operation
        }
        
        register_address = page_to_register.get(page)
        if not register_address:
            _LOGGER.error("Unknown page %d for loop mode", page)
            return False
        
        _LOGGER.info("Setting loop mode for page %d to %d", page, new_mode)
        
        from .modbus_registers import Register, RegisterType
        mode_register = Register(
            address=register_address,
            name=f"Loop_Mode_Page_{page}",
            reg_type=RegisterType.ENUM
        )
        
        return await self.write_register(mode_register, new_mode)

    async def async_set_main_temp_offset(self, new_value: float) -> bool:
        """Set main temperature offset (system-wide correction)."""
        # TODO: Find the Modbus register for main temp offset
        # This might not exist in Modbus or use a different mechanism
        _LOGGER.warning("Main temp offset not yet implemented for Modbus")
        return False

    async def async_set_antilegionella(self, enable: bool) -> bool:
        """Enable/disable anti-legionella function."""
        # TODO: Find the Modbus register for anti-legionella
        _LOGGER.warning("Anti-legionella control not yet implemented for Modbus")
        return False

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        """Enable/disable DHW circulation pump."""
        value = 1 if enable else 0
        _LOGGER.info("Setting DHW circulation to %s (value: %d)", "ON" if enable else "OFF", value)
        
        from .modbus_registers import Register, RegisterType
        circulation_register = Register(
            address=2328,
            name="DHW_Circulation",
            reg_type=RegisterType.BINARY
        )
        
        return await self.write_register(circulation_register, value)

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        """Enable/disable fast DHW heating."""
        value = 1 if enable else 0
        _LOGGER.info("Setting fast water heating to %s (value: %d)", "ON" if enable else "OFF", value)
        
        from .modbus_registers import Register, RegisterType
        fast_heating_register = Register(
            address=2015,
            name="Fast_DHW_Heating",
            reg_type=RegisterType.BINARY
        )
        
        return await self.write_register(fast_heating_register, value)

    async def async_set_reserve_source(self, enable: bool) -> bool:
        """Enable/disable reserve heating source."""
        # TODO: Find the Modbus register for reserve source
        _LOGGER.warning("Reserve source control not yet implemented for Modbus")
        return False

    async def async_set_additional_source(self, enable: bool) -> bool:
        """Enable/disable additional heating source."""
        value = 1 if enable else 0
        _LOGGER.info("Setting additional source to %s (value: %d)", "ON" if enable else "OFF", value)
        
        from .modbus_registers import Register, RegisterType
        additional_register = Register(
            address=2016,
            name="Additional_Source",
            reg_type=RegisterType.BINARY
        )
        
        return await self.write_register(additional_register, value)

    async def async_set_main_mode(self, new_mode: int) -> bool:
        """Set main operational mode (auto/comfort/eco)."""
        # Map to operation regime register (heating/cooling/off)
        # NOTE: This might not be the correct register for "operational mode"
        # The Cloud API uses "main_mode" which might be a different concept
        _LOGGER.info("Setting main mode to %d", new_mode)
        
        from .modbus_registers import Register, RegisterType
        mode_register = Register(
            address=2007,  # OPERATION_REGIME
            name="Main_Mode",
            reg_type=RegisterType.ENUM
        )
        
        return await self.write_register(mode_register, new_mode)

    async def async_shutdown(self) -> None:
        """Close Modbus connection."""
        if self.client and self._connected:
            _LOGGER.info("Closing Modbus connection")
            self.client.close()
            self._connected = False

"""
Kronoterm Modbus TCP Coordinator.

Handles communication with Kronoterm heat pump via Modbus TCP.
Alternative to cloud API for local control.
"""

import logging
import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
# All register definitions now come from kronoterm.json via RegisterMap
# No more hardcoded Python constants needed!
from .register_map import RegisterMap
from .modbus_reads import ModbusReadMixin
from .modbus_writes import ModbusWriteMixin

_LOGGER = logging.getLogger(__name__)

# Modbus unit ID (slave address)
DEFAULT_UNIT_ID = 20


class ModbusCoordinator(ModbusReadMixin, ModbusWriteMixin, DataUpdateCoordinator):
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

        # Load register map from JSON
        self.register_map: Optional[RegisterMap] = None
        try:
            json_path = Path(__file__).parent / "kronoterm.json"
            self.register_map = RegisterMap(json_path)
            _LOGGER.warning("✅ Loaded register map with %d registers from JSON", len(self.register_map.get_all()))
        except Exception as e:
            _LOGGER.warning("❌ Could not load register map: %s. Falling back to hardcoded registers.", e)

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

        # Scan interval (supports both seconds and legacy minutes)
        # Try new seconds-based setting first, fall back to minutes
        scan_interval_seconds = config_entry.options.get("scan_interval_seconds")
        if scan_interval_seconds is not None:
            scan_interval_seconds = max(scan_interval_seconds, 5)  # Min 5 seconds
            _LOGGER.info("Modbus coordinator update interval set to %d seconds", scan_interval_seconds)
            interval = timedelta(seconds=scan_interval_seconds)
        else:
            # Backwards compatibility: use minutes
            scan_interval_minutes = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            scan_interval_minutes = max(scan_interval_minutes, 1)
            _LOGGER.info("Modbus coordinator update interval set to %d minutes (legacy)", scan_interval_minutes)
            interval = timedelta(minutes=scan_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name="kronoterm_modbus_coordinator",
            update_method=self._async_update_data,
            update_interval=interval,
        )

    async def async_initialize(self) -> None:
        """Initialize Modbus connection and fetch device info."""
        _LOGGER.info("Initializing Modbus connection to %s:%s (unit_id=%s)", 
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
            _LOGGER.info("Initialization complete! Data has %d entries", len(self.data) if self.data else 0)
            
        except Exception as err:
            _LOGGER.error("Error during Modbus initialization: %s", err)
            self._connected = False
            raise UpdateFailed(f"Modbus initialization failed: {err}")

    async def _fetch_device_info(self) -> None:
        """Fetch device identification from Modbus."""
        try:
            # Read firmware version (address 5056) - not in JSON, read directly
            try:
                result = await self.client.read_holding_registers(5056 - 1, count=1, device_id=self.unit_id)
                firmware_raw = result.registers[0] if not result.isError() else None
                firmware = f"{firmware_raw}" if firmware_raw else "unknown"
            except Exception:
                firmware = "unknown"
            
            # Build device info
            model_name = self._format_model_name()
            
            # Use config_entry.entry_id as device identifier to maintain consistency
            # when switching between Cloud and Modbus connection types
            self.shared_device_info = {
                "identifiers": {(DOMAIN, self.config_entry.entry_id)},
                "name": "Kronoterm",
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
                "identifiers": {(DOMAIN, self.config_entry.entry_id)},
                "name": "Kronoterm",
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
        _LOGGER.debug("Update data called, connected=%s", self._connected)
        
        if not self._connected:
            raise UpdateFailed("Modbus client not connected")

        try:
            data = {}
            
            # Read registers using JSON-based register_map
            if not self.register_map:
                raise UpdateFailed("Register map not loaded - cannot read registers")
            
            # Always use register_map (no fallback)
            import time
            # Read both sensors AND control registers (switches need control register values)
            registers_to_read = self.register_map.get_sensors() + self.register_map.get_controls()
            _LOGGER.debug("Reading %d registers using batch reads", len(registers_to_read))
            
            start_time = time.time()
            
            # Group registers into consecutive batches for efficient reading
            batches = self._group_registers_into_batches(registers_to_read)
            _LOGGER.debug("Grouped into %d batches", len(batches))
            
            # Read all batches
            register_values = {}
            for batch_start, batch_count, batch_regs in batches:
                try:
                    # Read the entire batch in one Modbus request
                    modbus_address = batch_start - 1  # Apply -1 offset
                    result = await self.client.read_holding_registers(
                        modbus_address, count=batch_count, device_id=self.unit_id
                    )
                    
                    if result.isError():
                        _LOGGER.debug("Error reading batch at %d (count %d)", batch_start, batch_count)
                        continue
                    
                    # Map results back to individual registers
                    for i, reg_def in enumerate(batch_regs):
                        if reg_def.type == "Value32":
                            # For 32-bit registers, read both high and low
                            high_addr = reg_def.register32_high
                            low_addr = reg_def.register32_low
                            
                            high_offset = high_addr - batch_start
                            low_offset = low_addr - batch_start
                            
                            # Check if both registers are in the batch
                            if high_offset >= len(result.registers) or low_offset >= len(result.registers):
                                _LOGGER.warning("32-bit register %d out of batch range (batch_start=%d, offsets=%d/%d, len=%d)", 
                                               reg_def.address, batch_start, high_offset, low_offset, len(result.registers))
                                continue
                            
                            high_value = result.registers[high_offset]
                            low_value = result.registers[low_offset]
                            
                            _LOGGER.debug("32-bit %s: batch_start=%d, high_addr=%d (offset=%d, raw=%d), low_addr=%d (offset=%d, raw=%d)",
                                           reg_def.name_en, batch_start, high_addr, high_offset, high_value, 
                                           low_addr, low_offset, low_value)
                            
                            # Convert to signed integers
                            if high_value >= 32768:
                                high_value = high_value - 65536
                            if low_value >= 32768:
                                low_value = low_value - 65536
                            
                            # For Kronoterm: the actual value is in the LOW register!
                            # The naming in the manual is backwards - "high" register is actually low word
                            raw_value = low_value
                            
                            _LOGGER.debug("32-bit %s: final raw_value=%d (using LOW register)", reg_def.name_en, raw_value)
                        else:
                            addr = reg_def.address
                            offset = addr - batch_start
                            raw_value = result.registers[offset]
                            
                            # Convert to signed integer
                            if raw_value >= 32768:
                                raw_value = raw_value - 65536
                            
                        # Check for error values
                        if raw_value <= -500:
                            continue
                        
                        register_values[reg_def.address] = (reg_def, raw_value)
                
                except Exception as err:
                    _LOGGER.debug("Exception reading batch at %d: %s", batch_start, err)
                    continue
                
                read_time = time.time() - start_time
                _LOGGER.debug("Batch read took %.2fs for %d registers in %d batches", 
                              read_time, len(registers_to_read), len(batches))
                
                # Process results
                for reg_def, raw_value in register_values.values():
                    # Process based on register type
                    if reg_def.type == "Enum":
                        value = raw_value
                    elif reg_def.type == "Bitmask":
                        value = raw_value
                    elif reg_def.type in ("Status", "Control"):
                        value = raw_value
                    else:
                        # Scaled numeric value (Value or Value32)
                        if reg_def.scale and reg_def.scale != 1.0:
                            value = round(raw_value * reg_def.scale, 2)
                        else:
                            value = raw_value
                    
                    # Store in data dict using register address as key
                    data[reg_def.address] = {
                        "value": value,
                        "raw": raw_value,
                        "name": reg_def.name_en,
                        "unit": reg_def.unit,
                    }
                    
                    # Debug logging for critical sensors
                    if reg_def.address in [2371, 2372, 2327, 2103, 2001, 2007, 2023, 2187, 2191, 546, 553, 
                                          2130, 2160, 2110, 2161, 2102, 2024, 2051, 2188, 2189, 2190,
                                          2101, 2034, 2305]:  # return_temp, reservoir_current_setpoint, solar_reservoir_setpoint
                        _LOGGER.debug("Register %d (%s): raw=%d, scaled=%s, scale=%s", 
                                      reg_def.address, reg_def.name_en, raw_value, value, reg_def.scale)
            
            if not data:
                _LOGGER.error("No data collected from Modbus - all register reads failed")
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
            
            _LOGGER.debug("Successfully read %d registers from Modbus", len(modbus_reg_list))
            return formatted_data
            
        except ModbusException as err:
            _LOGGER.error("Modbus communication error: %s", err)
            raise UpdateFailed(f"Modbus error: {err}")
        except Exception as err:
            _LOGGER.error("Unexpected error during Modbus update: %s", err)
            raise UpdateFailed(f"Update failed: {err}")

    def _group_registers_into_batches(self, registers, max_gap=5, max_batch=100):
        """Group registers into consecutive batches for efficient Modbus reading.
        
        Args:
            registers: List of RegisterDefinition objects
            max_gap: Maximum gap between registers to include in same batch
            max_batch: Maximum number of registers per batch
            
        Returns:
            List of tuples: (batch_start_address, batch_count, list_of_register_defs)
        """
        if not registers:
            return []
        
        # Sort registers by address (use min of high/low for Value32 types)
        def get_sort_key(r):
            if r.type == "Value32":
                return min(r.register32_high, r.register32_low)
            return r.address
        
        sorted_regs = sorted(registers, key=get_sort_key)
        
        batches = []
        current_batch = [sorted_regs[0]]
        # For Value32, start at the minimum of high/low (should be high)
        if sorted_regs[0].type == "Value32":
            batch_start = min(sorted_regs[0].register32_high, sorted_regs[0].register32_low)
        else:
            batch_start = sorted_regs[0].address
        
        for reg in sorted_regs[1:]:
            if reg.type == "Value32":
                addr = min(reg.register32_high, reg.register32_low)
            else:
                addr = reg.address
            
            last_reg = current_batch[-1]
            if last_reg.type == "Value32":
                last_addr = max(last_reg.register32_high, last_reg.register32_low)
            else:
                last_addr = last_reg.address
            
            # Check if register fits in current batch
            gap = addr - last_addr
            batch_span = addr - batch_start + 1
            
            if gap <= max_gap and batch_span <= max_batch and len(current_batch) < max_batch:
                current_batch.append(reg)
            else:
                # Finalize current batch
                last_reg = current_batch[-1]
                if last_reg.type == "Value32":
                    # For 32-bit, need to include both high and low registers
                    last_reg_addr = max(last_reg.register32_high, last_reg.register32_low)
                else:
                    last_reg_addr = last_reg.address
                batch_count = last_reg_addr - batch_start + 1
                batches.append((batch_start, batch_count, current_batch))
                
                # Start new batch
                current_batch = [reg]
                batch_start = addr
        
        # Add final batch
        if current_batch:
            last_reg = current_batch[-1]
            if last_reg.type == "Value32":
                # For 32-bit, need to include both high and low registers
                last_reg_addr = max(last_reg.register32_high, last_reg.register32_low)
            else:
                last_reg_addr = last_reg.address
            batch_count = last_reg_addr - batch_start + 1
            batches.append((batch_start, batch_count, current_batch))
        
        return batches

    async def _read_register_with_def(self, address: int, reg_def) -> Optional[tuple]:
        """Read a register and return it with its definition for parallel processing.
        
        Returns:
            Tuple of (reg_def, raw_value) or None if read failed
        """
        try:
            raw_value = await self._read_register_address(address)
            if raw_value is None:
                return None
            return (reg_def, raw_value)
        except Exception as err:
            _LOGGER.debug("Error reading register %s (%d): %s", 
                         reg_def.name_en, reg_def.address, err)
            return None

    async def _read_register_address(self, address: int) -> Optional[int]:
        """Read a single register by address from Modbus device.
        
        Note: Kronoterm manual uses 1-based addressing, but pymodbus uses 0-based.
        We subtract 1 from the address to compensate.
        """
        try:
            # Compensate for addressing mode difference (manual is 1-based, pymodbus is 0-based)
            modbus_address = address - 1
            result = await self.client.read_holding_registers(
                modbus_address, count=1, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.debug("Error reading register %d: %s", address, result)
                return None
            
            value = result.registers[0]
            
            # Convert from unsigned 16-bit to signed 16-bit
            # Values > 32767 are negative in two's complement
            if value >= 32768:
                value = value - 65536
            
            # Check for typical error values (Kronoterm uses specific negative values for errors)
            # -600 (64936 unsigned) is a common "sensor not connected" value
            if value <= -500:  # Extremely low values indicate sensor errors
                _LOGGER.debug("Register %d returned error value %d (likely sensor disconnected)", address, value)
                return None
            
            return value
            
        except Exception as err:
            _LOGGER.debug("Exception reading register %d: %s", address, err)
            return None

    async def write_register_by_address(self, address: int, value: int) -> bool:
        """Write a value to a Modbus register by address (for generic number entities)."""
        if not self._connected:
            _LOGGER.error("Cannot write register: Modbus not connected")
            return False
        
        try:
            # Compensate for addressing mode difference (manual is 1-based, pymodbus is 0-based)
            modbus_address = address - 1
            
            # Convert signed to unsigned 16-bit if negative
            if value < 0:
                register_value = value + 65536  # Two's complement
            else:
                register_value = value
            
            _LOGGER.info("Writing value %d to register %d → modbus address %d (register value: %d)", 
                        value, address, modbus_address, register_value)
            
            result = await self.client.write_register(
                modbus_address, value=register_value, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.error("Error writing register %d: %s", address, result)
                return False
            
            # Request immediate refresh
            await self.async_request_refresh()
            
            return True
            
        except Exception as err:
            _LOGGER.error("Exception writing register %d: %s", address, err)
            return False

    def _update_feature_flags(self, data: Dict[str, Any]) -> None:
        """Update feature flags based on current data."""
        # Check if Loop 2 is installed (has valid temperature reading)
        # Valid range: -50°C to 100°C (after scaling by 0.1)
        # Raw values: -500 to 1000
        loop2_temp = data.get(2110, {}).get("value")
        self.loop2_installed = loop2_temp is not None and loop2_temp > -500
        
        # Check if Loop 3 is installed (has valid temperature reading)
        loop3_temp = data.get(2111, {}).get("value")
        self.loop3_installed = loop3_temp is not None and loop3_temp > -500
        
        # Check if Loop 4 is installed (has valid temperature reading)
        loop4_temp = data.get(2112, {}).get("value")
        self.loop4_installed = loop4_temp is not None and loop4_temp > -500
        
        # Check if Reservoir is installed (has valid setpoint reading)
        reservoir_setpoint = data.get(2034, {}).get("value")
        self.reservoir_installed = reservoir_setpoint is not None and reservoir_setpoint > 0
        
        # Debug logging
        _LOGGER.debug("Feature flags: loop2=%s, loop3=%s, loop4=%s, reservoir=%s (temps: %s, %s, %s, setpoint: %s)", 
                       self.loop2_installed, self.loop3_installed, self.loop4_installed, self.reservoir_installed,
                       loop2_temp, loop3_temp, loop4_temp, reservoir_setpoint)
        
        # Check if additional source is installed
        add_source = data.get(2002, {}).get("raw", 0)
        self.additional_source_installed = bool(add_source)

    async def async_shutdown(self) -> None:
        """Close Modbus connection."""
        if self.client and self._connected:
            _LOGGER.info("Closing Modbus connection")
            self.client.close()
            self._connected = False

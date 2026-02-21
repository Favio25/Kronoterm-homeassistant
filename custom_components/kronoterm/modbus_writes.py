"""
Kronoterm Modbus TCP - Write Operations.

Contains all write methods for the Modbus coordinator.
Extracted from modbus_coordinator.py for better organization.
"""

import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class ModbusWriteMixin:
    """Mixin class for Modbus write operations.
    
    Requires parent class to have:
    - self.register_map (RegisterMap instance)
    - self.client (AsyncModbusTcpClient)
    - self.unit_id (int)
    - self._connected (bool)
    - self.write_register_by_address(address, value) method
    """

    async def async_write_register(self, address: int, temperature: float) -> bool:
        """Write a temperature value to a Modbus register.
        
        Converts temperature (°C) to Modbus format (× 10).
        
        Args:
            address: Modbus register address
            temperature: Temperature in degrees Celsius
            
        Returns:
            True if successful, False otherwise
        """
        # Convert temperature to Modbus format (× 10)
        modbus_value = int(round(temperature * 10))
        
        _LOGGER.info("Writing temperature %.1f°C (modbus: %d) to register %d",
                    temperature, modbus_value, address)
        
        return await self.write_register_by_address(address, modbus_value)

    async def async_write_register_raw(self, address: int, value: int) -> bool:
        """Write a raw integer value to a Modbus register.

        Args:
            address: Modbus register address
            value: Raw integer value to write

        Returns:
            True if successful, False otherwise
        """
        _LOGGER.info("Writing raw value %d to register %d", value, address)
        return await self.write_register_by_address(address, int(value))

    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        """Set temperature setpoint for a loop or DHW based on page.
        
        Args:
            page: Cloud API page number (5=Loop1, 6=Loop2, 9=DHW)
            new_temp: Target temperature in °C
            
        Returns:
            True if successful, False otherwise
        """
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
        
        # Write directly using register_by_address (no need for Register object)
        return await self.write_register_by_address(register_address, modbus_value)

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """Set temperature offset (eco/comfort) for a loop or DHW.
        
        Args:
            page: Cloud API page number
            param_name: "circle_eco_offset" or "circle_comfort_offset"
            new_value: Offset value in °C
            
        Returns:
            True if successful, False otherwise
        """
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
        
        # Write directly using register_by_address (no need for Register object)
        return await self.write_register_by_address(register_address, modbus_value)

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """Enable/disable heat pump system operation (register 2012).
        
        Args:
            turn_on: True to turn on, False to turn off
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if turn_on else 0
        _LOGGER.info("Setting heat pump state to %s (value: %d)", "ON" if turn_on else "OFF", value)
        
        # Use register_map for JSON-based lookup (address 2012)
        reg = self.register_map.get_by_name("system_on") or self.register_map.get(2012)
        if not reg:
            _LOGGER.error("Register 2012 (system_on) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        """Set loop operation mode (off/normal/eco/comfort) based on page.
        
        Args:
            page: Cloud API page number
            new_mode: Mode value (varies by device)
            
        Returns:
            True if successful, False otherwise
        """
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
        
        # Write directly using register_by_address (no need for Register object)
        return await self.write_register_by_address(register_address, new_mode)

    async def async_set_main_temp_offset(self, new_value: float) -> bool:
        """Set main temperature correction (register 2014, scale=1).
        
        Note: This register uses scale=1, not 0.1!
        
        Args:
            new_value: Temperature correction in °C
            
        Returns:
            True if successful, False otherwise
        """
        # IMPORTANT: This register uses scale=1, not 0.1!
        # Value is in whole degrees Celsius
        modbus_value = int(round(new_value))
        
        _LOGGER.info("Setting main temperature correction to %d°C", modbus_value)
        
        # Use register_map for JSON-based lookup (address 2014)
        reg = self.register_map.get_by_name("system_temperature_correction") or self.register_map.get(2014)
        if not reg:
            _LOGGER.error("Register 2014 (system_temperature_correction) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, modbus_value)

    async def async_set_antilegionella(self, enable: bool) -> bool:
        """Enable/disable anti-legionella (thermal disinfection) function.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if enable else 0
        _LOGGER.info("Setting anti-legionella to %s (value: %d)", "ON" if enable else "OFF", value)
        
        # Use register_map for JSON-based lookup (address 2301)
        reg = self.register_map.get_by_name("thermal_disinfection") or self.register_map.get(2301)
        if not reg:
            _LOGGER.error("Register 2301 (thermal_disinfection) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        """Enable/disable DHW circulation pump.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if enable else 0
        _LOGGER.info("Setting DHW circulation to %s (value: %d)", "ON" if enable else "OFF", value)
        
        # Use register 2328 (dhw_circulation_pump)
        reg = self.register_map.get_by_name("dhw_circulation_pump") or self.register_map.get(2328)
        if not reg:
            _LOGGER.error("Register 2328 (dhw_circulation_pump) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        """Enable/disable fast DHW heating.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if enable else 0
        _LOGGER.info("Setting fast water heating to %s (value: %d)", "ON" if enable else "OFF", value)
        
        # Use register_map for JSON-based lookup (address 2015)
        reg = self.register_map.get_by_name("dhw_quick_heating_enable") or self.register_map.get(2015)
        if not reg:
            _LOGGER.error("Register 2015 (dhw_quick_heating_enable) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_reserve_source(self, enable: bool) -> bool:
        """Enable/disable reserve heating source.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if enable else 0
        _LOGGER.info("Setting reserve source to %s (value: %d)", "ON" if enable else "OFF", value)
        
        # Use register_map for JSON-based lookup (address 2018)
        reg = self.register_map.get_by_name("reserve_source_enable") or self.register_map.get(2018)
        if not reg:
            _LOGGER.error("Register 2018 (reserve_source_enable) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_additional_source(self, enable: bool) -> bool:
        """Enable/disable additional heating source.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        value = 1 if enable else 0
        _LOGGER.info("Setting additional source to %s (value: %d)", "ON" if enable else "OFF", value)
        
        # Use register_map for JSON-based lookup (address 2016)
        reg = self.register_map.get_by_name("additional_source_enable") or self.register_map.get(2016)
        if not reg:
            _LOGGER.error("Register 2016 (additional_source_enable) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, value)

    async def async_set_main_mode(self, new_mode: int) -> bool:
        """Set main operational mode (auto/comfort/eco).
        
        Args:
            new_mode: Mode value
            
        Returns:
            True if successful, False otherwise
        """
        _LOGGER.info("Setting program selection to %d", new_mode)
        
        # Use register_map for JSON-based lookup (address 2013)
        reg = self.register_map.get_by_name("operation_program_select") or self.register_map.get(2013)
        if not reg:
            _LOGGER.error("Register 2013 (operation_program_select) not found in register map")
            return False
        return await self.write_register_by_address(reg.address, new_mode)

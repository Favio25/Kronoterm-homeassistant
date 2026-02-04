"""
Kronoterm Modbus TCP - Read Operations.

Contains read helper methods for the Modbus coordinator.
Extracted from modbus_coordinator.py for better organization.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)


class ModbusReadMixin:
    """Mixin class for Modbus read operations.
    
    Requires parent class to have:
    - self.client (AsyncModbusTcpClient)
    - self.unit_id (int)
    - self._connected (bool)
    """

    def _group_registers_into_batches(
        self, 
        registers: List[Any], 
        max_gap: int = 5, 
        max_batch: int = 100
    ) -> List[Tuple[int, int, List[Any]]]:
        """Group consecutive registers into efficient read batches.
        
        Combines consecutive registers into batches to minimize Modbus requests.
        
        Args:
            registers: List of RegisterDefinition objects to batch
            max_gap: Maximum gap between registers to consider consecutive
            max_batch: Maximum number of registers in a single batch
            
        Returns:
            List of (batch_start_address, batch_count, batch_registers) tuples
        """
        if not registers:
            return []
        
        # Sort by address
        sorted_regs = sorted(registers, key=lambda r: r.address)
        
        batches = []
        current_batch = [sorted_regs[0]]
        batch_start = sorted_regs[0].address
        
        for reg in sorted_regs[1:]:
            # Check if this register can be added to current batch
            current_end = current_batch[-1].address
            gap = reg.address - current_end
            batch_size = len(current_batch)
            
            # Start new batch if:
            # - Gap is too large
            # - Batch is at max size
            if gap > max_gap or batch_size >= max_batch:
                # Save current batch
                batch_count = (current_batch[-1].address - batch_start) + 1
                batches.append((batch_start, batch_count, current_batch))
                
                # Start new batch
                current_batch = [reg]
                batch_start = reg.address
            else:
                # Add to current batch
                current_batch.append(reg)
        
        # Don't forget the last batch
        if current_batch:
            batch_count = (current_batch[-1].address - batch_start) + 1
            batches.append((batch_start, batch_count, current_batch))
        
        return batches

    async def _read_register_with_def(
        self, 
        address: int, 
        reg_def: Any
    ) -> Optional[Tuple[Any, int]]:
        """Read a register and return it with its definition for parallel processing.
        
        Args:
            address: Modbus register address
            reg_def: RegisterDefinition object
            
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
        
        Args:
            address: Modbus register address (1-based, from Kronoterm manual)
            
        Returns:
            Register value as signed integer, or None if read failed
        """
        if not self._connected:
            return None
        
        try:
            # Compensate for addressing mode difference (manual is 1-based, pymodbus is 0-based)
            modbus_address = address - 1
            
            result = await self.client.read_holding_registers(
                modbus_address, count=1, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.debug("Error reading register %d (modbus addr %d)", address, modbus_address)
                return None
            
            raw_value = result.registers[0]
            
            # Convert to signed integer if needed
            if raw_value >= 32768:
                raw_value = raw_value - 65536
            
            return raw_value
            
        except Exception as err:
            _LOGGER.debug("Exception reading register %d: %s", address, err)
            return None

    async def write_register_by_address(self, address: int, value: int) -> bool:
        """Write a value to a Modbus register by address.
        
        Note: Kronoterm manual uses 1-based addressing, but pymodbus uses 0-based.
        We subtract 1 from the address to compensate (same as reads).
        
        Args:
            address: Modbus register address (1-based)
            value: Value to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            _LOGGER.error("Cannot write register: Modbus not connected")
            return False
        
        try:
            # Compensate for addressing mode difference (manual is 1-based, pymodbus is 0-based)
            modbus_address = address - 1
            
            _LOGGER.info("Writing value %d to register %d (modbus address %d)", 
                        value, address, modbus_address)
            
            result = await self.client.write_register(
                modbus_address, value=value, device_id=self.unit_id
            )
            
            if result.isError():
                _LOGGER.error("Error writing to register %d: %s", address, result)
                return False
            
            _LOGGER.info("Successfully wrote value %d to register %d", value, address)
            return True
            
        except Exception as err:
            _LOGGER.error("Exception writing to register %d: %s", address, err)
            return False

    def get_register_value(self, address: int) -> Optional[Any]:
        """Get current value of a register from cached data by address.
        
        Args:
            address: Modbus register address
            
        Returns:
            Register value from cache, or None if not found
        """
        if not self.data:
            return None
        
        # Data is now in format: {"main": {"ModbusReg": [...]}}
        modbus_reg_list = self.data.get("main", {}).get("ModbusReg", [])
        for reg in modbus_reg_list:
            if reg.get("address") == address:
                return reg.get("value")
        
        return None

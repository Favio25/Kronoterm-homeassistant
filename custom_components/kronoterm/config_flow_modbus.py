"""
Config flow additions for Modbus TCP support.

This file extends the existing config_flow.py to support Modbus TCP connection.
"""

import logging
import voluptuous as vol
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from pymodbus.client import AsyncModbusTcpClient

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Connection types
CONNECTION_TYPE_CLOUD = "cloud"
CONNECTION_TYPE_MODBUS = "modbus"

# Model options for Modbus (required for energy calculation)
MODEL_OPTIONS = {
    "adapt_0312": "ADAPT 0312 (up to 3.5 kW)",
    "adapt_0416": "ADAPT 0416 (up to 5 kW)",
    "adapt_0724": "ADAPT 0724 (up to 7 kW)",
    "unknown": "Unknown (no energy calculation)",
}


async def validate_modbus_connection(data: Dict[str, Any]) -> str | None:
    """
    Validate Modbus connection using AsyncModbusTcpClient.
    Returns an error code string on failure, or None on success.
    """
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, 502)
    unit_id = data.get("unit_id", 20)
    
    _LOGGER.debug("Validating Modbus connection to %s:%s, unit %s", host, port, unit_id)
    
    try:
        # Use async client (same as coordinator will use)
        client = AsyncModbusTcpClient(host=host, port=port)
        
        # Try to connect
        connected = await client.connect()
        if not connected:
            _LOGGER.warning("Modbus connection failed to %s:%s", host, port)
            client.close()
            return "cannot_connect"
        
        _LOGGER.debug("Connected successfully, testing read...")
        
        # Try to read a known register (outdoor temp at 2102)
        # Use POSITIONAL arguments for compatibility with all pymodbus versions
        result = await client.read_holding_registers(2102, count=1, device_id=unit_id)
        
        # Close connection
        client.close()
        
        if result.isError():
            _LOGGER.warning("Modbus read test failed: %s", result)
            return "cannot_read"
        
        _LOGGER.info("Modbus connection validated successfully. Read value: %s", result.registers[0])
        return None  # Success
        
    except Exception as err:
        _LOGGER.error("Modbus validation error: %s", err)
        import traceback
        _LOGGER.error("Full traceback:\n%s", traceback.format_exc())
        return "unknown"


def get_connection_type_schema() -> vol.Schema:
    """Get schema for connection type selection."""
    return vol.Schema({
        vol.Required("connection_type", default=CONNECTION_TYPE_CLOUD): vol.In({
            CONNECTION_TYPE_CLOUD: "Cloud API (Internet required)",
            CONNECTION_TYPE_MODBUS: "Modbus TCP (Local network)",
        }),
    })


def get_modbus_schema(defaults: Dict[str, Any] = None) -> vol.Schema:
    """Get schema for Modbus TCP configuration."""
    defaults = defaults or {}
    
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, 502)): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional("unit_id", default=defaults.get("unit_id", 20)): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
    })


# This would be used to extend the existing KronotermConfigFlow class
# by adding a step to choose connection type, then branching to either
# cloud or modbus configuration steps.

def create_user_step_with_connection_choice(original_async_step_user):
    """
    Decorator to modify the user step to include connection type selection.
    
    This is a pattern for extending the existing config_flow without
    completely rewriting it.
    """
    async def async_step_user_with_choice(self, user_input=None):
        """Handle user step with connection type choice."""
        if user_input is not None and "connection_type" in user_input:
            # Store connection type and move to appropriate step
            self.connection_type = user_input["connection_type"]
            
            if self.connection_type == CONNECTION_TYPE_MODBUS:
                return await self.async_step_modbus()
            else:
                return await original_async_step_user(self, None)
        
        # Show connection type selection
        return self.async_show_form(
            step_id="user",
            data_schema=get_connection_type_schema(),
        )
    
    return async_step_user_with_choice

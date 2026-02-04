import logging
from dataclasses import dataclass
from typing import List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entities import KronotermBinarySensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class BinarySensorConfig:
    """Configuration for a Kronoterm binary sensor."""
    address: int
    name_key: str  # Translation key
    bit: Optional[int] = None
    icon: Optional[str] = None
    install_flag: Optional[str] = None # Coordinator attribute to check, if applicable


BINARY_SENSOR_DEFINITIONS: List[BinarySensorConfig] = [
    # Circulation Pumps
    BinarySensorConfig(2038, "main_pump_status", icon="mdi:pump"),
    BinarySensorConfig(2045, "circulation_loop_1", icon="mdi:pump", install_flag="loop1_installed"),
    BinarySensorConfig(2055, "circulation_loop_2", icon="mdi:pump", install_flag="loop2_installed"),
    # !!! UPDATE XXXX WITH CORRECT MODBUS ADDRESS !!!
    BinarySensorConfig(2065, "circulation_loop_3", icon="mdi:pump", install_flag="loop3_installed"),
    # !!! UPDATE YYYY WITH CORRECT MODBUS ADDRESS !!!
    BinarySensorConfig(2075, "circulation_loop_4", icon="mdi:pump", install_flag="loop4_installed"),
    BinarySensorConfig(2028, "circulation_dhw", bit=0, icon="mdi:pump", install_flag="tap_water_installed"), # Assuming 'tap_water_installed' flag exists

    # System status
    BinarySensorConfig(2011, "defrost_status", icon="mdi:snowflake-melt"),
    
    # Other flags
    BinarySensorConfig(2002, "additional_source", bit=0, icon="mdi:fire"), # No install flag needed for this one
    
    # Example: Add thermostat flags if needed
    # BinarySensorConfig(LOOP1_THERMOSTAT_FLAG_ADDR, "thermostat_loop_1", icon="mdi:thermostat", install_flag="loop1_installed"),
    # BinarySensorConfig(LOOP2_THERMOSTAT_FLAG_ADDR, "thermostat_loop_2", icon="mdi:thermostat", install_flag="loop2_installed"),
    # BinarySensorConfig(LOOP3_THERMOSTAT_FLAG_ADDR, "thermostat_loop_3", icon="mdi:thermostat", install_flag="loop3_installed"),
    # BinarySensorConfig(LOOP4_THERMOSTAT_FLAG_ADDR, "thermostat_loop_4", icon="mdi:thermostat", install_flag="loop4_installed"),
]


async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> bool:
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("No data found in hass.data for domain %s", DOMAIN)
        return False

    coordinator = data.get(config_entry.entry_id)
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    shared_device_info = coordinator.shared_device_info

    # Get the list of all addresses reported by the heat pump
    modbus_list = (coordinator.data or {}).get("main", {}).get("ModbusReg", [])
    available_addresses = {reg.get("address") for reg in modbus_list}

    binary_sensors = []
    for config in BINARY_SENSOR_DEFINITIONS:
        
        # Check if the feature is installed, if applicable
        is_installed = True # Default to True if no flag specified
        if config.install_flag:
            is_installed = getattr(coordinator, config.install_flag, False)

        # Check if the specific Modbus address is reported by the pump
        is_available = config.address in available_addresses

        if is_installed and is_available:
            binary_sensors.append(
                KronotermBinarySensor(
                    coordinator=coordinator,
                    address=config.address,
                    name=config.name_key,  # Pass the translation key
                    device_info=shared_device_info,
                    bit=config.bit,
                    icon=config.icon
                )
            )
        else:
             _LOGGER.info(
                "Skipping entity %s: Installed=%s, Address %s Available=%s",
                config.name_key,
                is_installed,
                config.address,
                is_available,
            )

    async_add_entities(binary_sensors, update_before_add=False)
    return True
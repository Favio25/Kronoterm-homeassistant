import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .entities import KronotermBinarySensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up the Kronoterm binary sensor platform."""
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("No data found in hass.data for domain %s", DOMAIN)
        return False

    coordinator = data.get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data for domain %s", DOMAIN)
        return False

    shared_device_info = coordinator.shared_device_info

    # Define binary sensors
    binary_sensors = [
        KronotermBinarySensor(
            coordinator.main_coordinator, 2000, "Heat Pump ON/OFF", shared_device_info, icon="mdi:power"
        ),
        KronotermBinarySensor(
            coordinator.main_coordinator, 2045, "Loop 1 Circulation", shared_device_info, icon="mdi:pump"
        ),
        KronotermBinarySensor(
            coordinator.main_coordinator, 2055, "Loop 2 Circulation", shared_device_info, icon="mdi:pump"
        ),
        KronotermBinarySensor(
            coordinator.main_coordinator, 2002, "Additional Source", shared_device_info, bit=0, icon="mdi:fire"
        ),
        KronotermBinarySensor(
            coordinator.main_coordinator, 2028, "DHW Circulation", shared_device_info, bit=0, icon="mdi:pump"
        ),
    ]

    async_add_entities(binary_sensors)
    return True

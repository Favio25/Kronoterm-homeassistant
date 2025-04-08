import logging
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import KronotermBinarySensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DEFINITIONS = [
    # (address, name, bit, icon)
    (2045, "Loop 1 Circulation", None, "mdi:pump"),
    (2055, "Loop 2 Circulation", None, "mdi:pump"),
    (2002, "Additional Source", 0, "mdi:fire"),  # uses bit=0
    (2028, "DHW Circulation", 0, "mdi:pump"),
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

    coordinator = data.get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    shared_device_info = coordinator.shared_device_info

    binary_sensors = []
    for (address, name, bit, icon) in BINARY_SENSOR_DEFINITIONS:
        binary_sensors.append(
            KronotermBinarySensor(
                coordinator=coordinator,
                address=address,
                name=name,
                device_info=shared_device_info,
                bit=bit,
                icon=icon
            )
        )

    async_add_entities(binary_sensors, update_before_add=True)
    return True
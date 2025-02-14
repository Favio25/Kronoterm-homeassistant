import logging
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entities import KronotermBinarySensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# For cleaner organization, you can store your sensor definitions in a list
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
    """
    Set up the Kronoterm binary sensor platform for a given config entry.

    1. Retrieves the Kronoterm coordinator from hass.data.
    2. Creates a list of binary sensor entities for each defined register/bit.
    3. Adds them to Home Assistant.
    """
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("No data found in hass.data for domain %s", DOMAIN)
        return False

    coordinator = data.get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    # Pull a reference to the main_coordinator for sensor data,
    # or if your code uses coordinator.main_coordinator
    main_coordinator = getattr(coordinator, "main_coordinator", None)
    if not main_coordinator:
        _LOGGER.error("No main_coordinator found in Kronoterm coordinator.")
        return False

    # Shared device info for all entities, so they group under one device
    shared_device_info = coordinator.shared_device_info

    # Build the list of KronotermBinarySensor entities
    binary_sensors: List[KronotermBinarySensor] = []
    for (address, name, bit, icon) in BINARY_SENSOR_DEFINITIONS:
        binary_sensors.append(
            KronotermBinarySensor(
                coordinator=main_coordinator,
                address=address,
                name=name,
                device_info=shared_device_info,
                bit=bit,            # None if not using bitmasks
                icon=icon
            )
        )

    # Optionally log how many binary sensors are being added
    _LOGGER.debug("Adding %d Kronoterm binary sensors", len(binary_sensors))

    async_add_entities(binary_sensors, update_before_add=True)
    return True

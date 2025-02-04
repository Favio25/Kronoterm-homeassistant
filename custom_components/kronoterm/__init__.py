import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .coordinator import KronotermCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Kronoterm from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Use Home Assistant's built-in client session
    session = async_get_clientsession(hass)

    # Pass the entire config entry to the coordinator so it can extract credentials securely.
    coordinator = KronotermCoordinator(hass, session, entry)

    try:
        await coordinator.async_initialize()
    except Exception as err:
        _LOGGER.error("Error initializing Kronoterm coordinator: %s", err, exc_info=True)
        return False

    hass.data[DOMAIN]["coordinator"] = coordinator

    # Forward the setup to the sensor and binary_sensor platforms.
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "switch", "climate"])

    return True

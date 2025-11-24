import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN
from .coordinator import KronotermCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "climate", "select", "number"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Kronoterm component."""
    # This integration is configured via config entries, so setup here is minimal.
    # Returning True signals HA that the component is async-safe to load.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Kronoterm integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Use Home Assistant's built-in client session.
    session = async_get_clientsession(hass)

    # Initialize the coordinator with the entire config entry to securely extract credentials.
    coordinator = KronotermCoordinator(hass, session, entry)

    try:
        await coordinator.async_initialize()
    except Exception as err:
        _LOGGER.error("Error initializing Kronoterm coordinator: %s", err, exc_info=True)
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN]["coordinator"] = coordinator

    # Forward the setup to the required platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Kronoterm integration set up successfully for entry %s", entry.entry_id)
    return True
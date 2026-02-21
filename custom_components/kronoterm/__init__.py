import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN
from .coordinator import KronotermMainCoordinator, KronotermDHWCoordinator
from .modbus_coordinator import ModbusCoordinator
from .config_flow_modbus import CONNECTION_TYPE_MODBUS

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

    # Check connection type and create appropriate coordinator
    connection_type = entry.data.get("connection_type", "cloud")
    system_type = entry.data.get("system_type", "cloud")
    
    if connection_type == CONNECTION_TYPE_MODBUS:
        _LOGGER.info("Setting up Kronoterm with Modbus TCP connection")
        coordinator = ModbusCoordinator(hass, entry)
    elif system_type == "dhw":
        _LOGGER.info("Setting up Kronoterm DHW (Water Cloud) connection")
        # Create a new client session for DHW to ensure isolation
        # We don't use the shared hass session to avoid cookie conflicts with main cloud
        from homeassistant.helpers.aiohttp_client import async_create_clientsession
        session = async_create_clientsession(hass, cookie_jar=None) # Default jar is fine if new session
        coordinator = KronotermDHWCoordinator(hass, session, entry)
    else:
        _LOGGER.info("Setting up Kronoterm with Cloud API connection")
        # Use Home Assistant's built-in client session for main cloud API
        session = async_get_clientsession(hass)
        coordinator = KronotermMainCoordinator(hass, session, entry)

    try:
        await coordinator.async_initialize()
    except Exception as err:
        _LOGGER.error("Error initializing Kronoterm coordinator: %s", err, exc_info=True)
        raise ConfigEntryNotReady from err

    # Store coordinator using entry_id as key to support multiple instances
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.info("Stored coordinator for entry %s (%s)", entry.entry_id, connection_type)

    # Forward the setup to the required platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Kronoterm integration set up successfully for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Kronoterm integration for entry %s", entry.entry_id)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up coordinator for this specific entry
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator and hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()
        
        # Remove data for this entry
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("Kronoterm integration unloaded successfully for entry %s", entry.entry_id)
    
    return unload_ok
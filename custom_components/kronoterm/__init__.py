import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from .const import CONFIG_ENTRY_VERSION, DOMAIN
from .coordinator import KronotermMainCoordinator, KronotermDHWCoordinator
from .modbus_coordinator import ModbusCoordinator
from .config_flow_modbus import CONNECTION_TYPE_MODBUS
from .identifiers import (
    config_unique_id_from_data,
    legacy_energy_unique_id_migrations,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "climate", "select", "number", "button", "text"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)

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
        session = async_create_clientsession(hass)
        coordinator = KronotermDHWCoordinator(hass, session, entry)
    else:
        _LOGGER.info("Setting up Kronoterm with Cloud API connection")
        # Each Cloud entry needs its own cookie jar. Sharing Home Assistant's
        # global session lets one account overwrite another account's PHPSESSID.
        session = async_create_clientsession(hass)
        coordinator = KronotermMainCoordinator(hass, session, entry)

    try:
        await coordinator.async_initialize()
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        _LOGGER.error("Error initializing Kronoterm coordinator: %s", err, exc_info=True)
        raise ConfigEntryNotReady from err

    # Store coordinator using entry_id as key to support multiple instances
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.info("Stored coordinator for entry %s (%s)", entry.entry_id, connection_type)

    # Forward the setup to the required platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entity identifiers without changing users' entity IDs."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    registry = er.async_get(hass)

    if entry.version < 2 and entry.data.get("system_type") == "dhw":
        canonical_unique_id = f"{entry.entry_id}_{DOMAIN}_dhw_current_temperature"
        duplicate_unique_id = f"{entry.entry_id}_{DOMAIN}_dhw_boiler_temp"
        canonical_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, canonical_unique_id
        )
        duplicate_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, duplicate_unique_id
        )

        if duplicate_entity_id and canonical_entity_id:
            registry.async_remove(duplicate_entity_id)
            _LOGGER.info("Removed duplicate DHW boiler temperature registry entry")
        elif duplicate_entity_id:
            registry.async_update_entity(
                duplicate_entity_id,
                new_unique_id=canonical_unique_id,
            )
            _LOGGER.info("Migrated DHW boiler temperature entity to canonical unique ID")

    if (
        entry.version < 3
        and entry.data.get("connection_type", "cloud") != CONNECTION_TYPE_MODBUS
        and entry.data.get("system_type", "cloud") != "dhw"
    ):
        for old_unique_id, new_unique_id in legacy_energy_unique_id_migrations(
            entry.entry_id
        ).items():
            old_entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, old_unique_id
            )
            if not old_entity_id:
                continue

            old_entry = registry.async_get(old_entity_id)
            if old_entry and old_entry.config_entry_id not in (None, entry.entry_id):
                continue

            new_entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, new_unique_id
            )
            if new_entity_id and new_entity_id != old_entity_id:
                registry.async_remove(old_entity_id)
                continue

            registry.async_update_entity(
                old_entity_id,
                new_unique_id=new_unique_id,
            )
            _LOGGER.info(
                "Migrated energy entity %s to an entry-scoped unique ID",
                old_entity_id,
            )

    update_kwargs = {"version": CONFIG_ENTRY_VERSION}
    if entry.unique_id is None:
        candidate_unique_id = config_unique_id_from_data(entry.data)
        other_unique_ids = {
            other.unique_id
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id and other.unique_id is not None
        }
        if candidate_unique_id and candidate_unique_id not in other_unique_ids:
            update_kwargs["unique_id"] = candidate_unique_id
            _LOGGER.info("Assigned a stable unique ID to the config entry")

    hass.config_entries.async_update_entry(entry, **update_kwargs)
    return True

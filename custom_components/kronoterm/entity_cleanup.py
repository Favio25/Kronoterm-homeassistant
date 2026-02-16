"""Entity cleanup helpers for Cloud/Modbus mode switching."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# Entities that only exist in Cloud API mode
CLOUD_ONLY_ENTITIES = [
    # Add Cloud-specific entities here if any are identified
    # Currently, Cloud and Modbus have good feature parity
]

# Entities that only exist in Modbus TCP mode
MODBUS_ONLY_ENTITIES = [
    # Binary sensors (status indicators)
    "binary_sensor.kronoterm_main_pump_status",
    "binary_sensor.kronoterm_circulation_loop_1",
    "binary_sensor.kronoterm_circulation_loop_2",
    "binary_sensor.kronoterm_circulation_loop_3",
    "binary_sensor.kronoterm_circulation_loop_4",
    "binary_sensor.kronoterm_circulation_pump",
    "binary_sensor.kronoterm_dhw_circulation_pump",
    "binary_sensor.kronoterm_defrost_status",
    "binary_sensor.kronoterm_reserve_source_status",
    "binary_sensor.kronoterm_alternative_source_status",
    "binary_sensor.kronoterm_alternative_source_pump",
    "binary_sensor.kronoterm_additional_source",
]


async def disable_mode_specific_entities(
    hass: HomeAssistant,
    entry_id: str,
    switching_to_mode: str
) -> None:
    """Disable entities that don't exist in the target mode.
    
    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        switching_to_mode: Either "cloud" or "modbus"
    """
    registry = er.async_get(hass)
    
    # Determine which entities to disable
    if switching_to_mode == "cloud":
        entities_to_disable = MODBUS_ONLY_ENTITIES
        _LOGGER.info("Switching to Cloud API - will disable %d Modbus-only entities", 
                     len(entities_to_disable))
    elif switching_to_mode == "modbus":
        entities_to_disable = CLOUD_ONLY_ENTITIES
        _LOGGER.info("Switching to Modbus TCP - will disable %d Cloud-only entities", 
                     len(entities_to_disable))
    else:
        _LOGGER.warning("Unknown mode: %s", switching_to_mode)
        return
    
    disabled_count = 0
    
    # Iterate through all entities for this integration entry
    for entity_id in list(registry.entities):
        entity_entry = registry.entities.get(entity_id)
        
        # Skip if not from this config entry
        if not entity_entry or entity_entry.config_entry_id != entry_id:
            continue
        
        # Check if this entity should be disabled
        if entity_id in entities_to_disable:
            if entity_entry.disabled_by != er.RegistryEntryDisabler.INTEGRATION:
                _LOGGER.debug("Disabling entity: %s", entity_id)
                registry.async_update_entity(
                    entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
                disabled_count += 1
    
    if disabled_count > 0:
        _LOGGER.info("Disabled %d entities that don't exist in %s mode", 
                     disabled_count, switching_to_mode)


async def enable_mode_specific_entities(
    hass: HomeAssistant,
    entry_id: str,
    switching_to_mode: str
) -> None:
    """Re-enable entities that exist in the target mode.
    
    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        switching_to_mode: Either "cloud" or "modbus"
    """
    registry = er.async_get(hass)
    
    # Determine which entities to re-enable
    if switching_to_mode == "modbus":
        entities_to_enable = MODBUS_ONLY_ENTITIES
        _LOGGER.info("Switching to Modbus TCP - will re-enable %d Modbus entities", 
                     len(entities_to_enable))
    elif switching_to_mode == "cloud":
        entities_to_enable = CLOUD_ONLY_ENTITIES
        _LOGGER.info("Switching to Cloud API - will re-enable %d Cloud entities", 
                     len(entities_to_enable))
    else:
        _LOGGER.warning("Unknown mode: %s", switching_to_mode)
        return
    
    enabled_count = 0
    
    # Iterate through all entities for this integration entry
    for entity_id in list(registry.entities):
        entity_entry = registry.entities.get(entity_id)
        
        # Skip if not from this config entry
        if not entity_entry or entity_entry.config_entry_id != entry_id:
            continue
        
        # Check if this entity should be re-enabled
        if entity_id in entities_to_enable:
            if entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                _LOGGER.debug("Re-enabling entity: %s", entity_id)
                registry.async_update_entity(
                    entity_id,
                    disabled_by=None
                )
                enabled_count += 1
    
    if enabled_count > 0:
        _LOGGER.info("Re-enabled %d entities for %s mode", 
                     enabled_count, switching_to_mode)

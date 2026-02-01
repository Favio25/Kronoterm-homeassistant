import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_MODE_OPTIONS
from .entities import KronotermModbusBase  # Import the base class
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class SelectConfig:
    """A container for select entity configuration."""
    name: str  # User-facing name, e.g., "Loop 1 Operation"
    address: int
    page: int
    install_flag: str  # Coordinator attribute to check (e.g., "loop1_installed")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kronoterm select entities for different operations."""
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return

    # Get the list of all addresses reported by the heat pump
    modbus_list = (coordinator.data or {}).get("main", {}).get("ModbusReg", [])
    available_addresses = {reg.get("address") for reg in modbus_list}

    # Define the configuration for each select entity.
    entity_configs: List[SelectConfig] = [
        SelectConfig("Loop 1 Operation", 2042, 5, "loop1_installed"),
        SelectConfig("Loop 2 Operation", 2052, 6, "loop2_installed"),
        SelectConfig("Sanitary Water Operation", 2026, 9, "tap_water_installed"), # Assuming 'tap_water_installed'
        SelectConfig("Loop 3 Operation", 2062, 7, "loop3_installed"),
        SelectConfig("Loop 4 Operation", 2072, 8, "loop4_installed"),
    ]

    entities = []
    for config in entity_configs:
        # Check if the feature is installed (e.g., coordinator.loop1_installed)
        is_installed = getattr(coordinator, config.install_flag, False)

        # Check if the specific Modbus address is reported by the pump
        is_available = config.address in available_addresses
        
        if is_installed and is_available:
            entities.append(
                KronotermModeSelect(
                    entry=entry,
                    name=config.name,
                    address=config.address,
                    page=config.page,
                    coordinator=coordinator,
                )
            )
        else:
            _LOGGER.info(
                "Skipping entity %s: Installed=%s, Address %s Available=%s",
                config.name,
                is_installed,
                config.address,
                is_available,
            )

    # Add operational mode select (ECO/Auto/Comfort)
    entities.append(KronotermOperationalModeSelect(entry, coordinator))
    
    async_add_entities(entities, update_before_add=True)


class KronotermModeSelect(KronotermModbusBase, SelectEntity):
    """
    Select entity for Kronoterm offering three options: OFF, ON, AUTO.
    
    Reads the current mode from a Modbus register via KronotermModbusBase.
    Changing the selection calls coordinator.async_set_loop_mode_by_page.
    """

    _attr_options = ["OFF", "ON", "AUTO"]

    # Mapping for converting register values to select options.
    VALUE_TO_OPTION = {0: "OFF", 1: "ON", 2: "AUTO"}
    OPTION_TO_VALUE = {"OFF": 0, "ON": 1, "AUTO": 2}

    def __init__(
        self,
        entry: ConfigEntry,
        name: str,
        address: int,
        page: int,
        coordinator: Any,
    ) -> None:
        """Initialize the Kronoterm select entity."""
        # Convert name to translation key
        translation_key = name.lower().replace(" ", "_")
        
        # Initialize the base class
        super().__init__(coordinator, address, translation_key, coordinator.shared_device_info)
        
        self._entry = entry
        self._page = page
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{address}_mode"

    def _process_value(self, raw_value: Any) -> Optional[str]:
        """Process the raw modbus value and map it to an option string."""
        if raw_value is None:
            return None
        
        try:
            # Use int(float()) to handle "2.0" or "2"
            val = int(float(raw_value))
            return self.VALUE_TO_OPTION.get(val)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Could not map enum value '%s' for sensor %s (address %s)",
                raw_value,
                self._name_key,
                self._address
            )
            return None

    @property
    def current_option(self) -> Optional[str]:
        """Return the current option ('OFF', 'ON', or 'AUTO') by processing the Modbus value."""
        return self._compute_value()

    async def async_select_option(self, option: str) -> None:
        """
        Map the selected option to its corresponding register value and update the mode.
        
        Logs an error if the option is unknown or if updating fails.
        """
        new_mode = self.OPTION_TO_VALUE.get(option)
        if new_mode is None:
            _LOGGER.warning("Unknown option: %s", option)
            return

        success = await self.coordinator.async_set_loop_mode_by_page(self._page, new_mode)
        if not success:
            _LOGGER.error("Failed to set mode for %s", self._attr_translation_key)
        # No need to request refresh here, async_set_loop_mode_by_page does it

class KronotermOperationalModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for Kronoterm operational mode (ECO/Auto/Comfort)."""

    def __init__(self, entry: ConfigEntry, coordinator: Any) -> None:
        """Initialize the operational mode select entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_translation_key = "operational_mode"
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_operational_mode"
        self._attr_device_info = coordinator.shared_device_info
        
        # MAIN_MODE_OPTIONS maps integer → string: {0: "auto", 1: "comfort", 2: "eco"}
        # For reading (int → string): Use MAIN_MODE_OPTIONS directly
        # For writing (string → int): Create reverse mapping
        self.OPTION_TO_VALUE = {v: k for k, v in MAIN_MODE_OPTIONS.items()}  # {"auto": 0, "comfort": 1, "eco": 2}
        
        # Options are the string values from MAIN_MODE_OPTIONS
        self._attr_options = list(MAIN_MODE_OPTIONS.values())

    @property
    def current_option(self) -> Optional[str]:
        """Return the current operational mode."""
        if not self.coordinator.data:
            return None
        
        # Try to get from main_settings first
        main_settings = self.coordinator.data.get("main_settings", {})
        advanced_settings = main_settings.get("AdvancedSettings", {})
        mode_value = advanced_settings.get("main_mode")
        
        # Fallback to TemperaturesAndConfig if not in AdvancedSettings
        if mode_value is None:
            temps_config = main_settings.get("TemperaturesAndConfig", {})
            mode_value = temps_config.get("main_mode")
        
        if mode_value is None:
            return None
        
        try:
            mode_int = int(mode_value)
            # Convert integer to string: 0 → "auto", 1 → "comfort", 2 → "eco"
            return MAIN_MODE_OPTIONS.get(mode_int)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not parse main_mode value: %s", mode_value)
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the operational mode."""
        # Convert string to integer: "auto" → 0, "comfort" → 1, "eco" → 2
        new_mode = self.OPTION_TO_VALUE.get(option)
        if new_mode is None:
            _LOGGER.warning("Unknown operational mode option: %s", option)
            return

        success = await self.coordinator.async_set_main_mode(new_mode)
        if not success:
            _LOGGER.error("Failed to set operational mode to %s", option)

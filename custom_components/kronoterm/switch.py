import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Kronoterm switch."""
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator
    async_add_entities([KronotermHeatPumpSwitch(hass, parent_coordinator, main_coordinator)])
    return True

class KronotermHeatPumpSwitch(CoordinatorEntity, SwitchEntity):
    """Kronoterm heat pump switch entity."""

    def __init__(self, hass: HomeAssistant, parent_coordinator, coordinator: DataUpdateCoordinator):
        """Initialize switch and get initial state."""
        super().__init__(coordinator)
        self._parent_coordinator = parent_coordinator
        self.hass = hass
        self._attr_name = "Heat Pump ON/OFF"
        self._attr_unique_id = f"{DOMAIN}_heatpump_switch"

        # ✅ Initialize state correctly at startup
        self._attr_is_on = self._get_initial_state()

    def _get_initial_state(self) -> bool:
        """Get initial state from binary sensor or last known state."""
        state = self.hass.states.get("binary_sensor.heat_pump_on_off")
        if state:
            return state.state == "on"
        return False  # Default if state is unavailable

    @property
    def is_on(self) -> bool:
        """Return assumed heat pump state."""
        return self._attr_is_on  # Use locally stored state

    async def async_turn_on(self, **kwargs):
        """Turn on heat pump and assume state is ON."""
        if await self._parent_coordinator.async_set_heatpump_state(True):
            self._attr_is_on = True  # Assume state is ON
            self.async_write_ha_state()  # Notify Home Assistant of the change
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on the heat pump.")

    async def async_turn_off(self, **kwargs):
        """Turn off heat pump and assume state is OFF."""
        if await self._parent_coordinator.async_set_heatpump_state(False):
            self._attr_is_on = False  # Assume state is OFF
            self.async_write_ha_state()  # Notify Home Assistant of the change
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off the heat pump.")

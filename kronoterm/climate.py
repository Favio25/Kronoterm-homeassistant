import logging
import aiohttp
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Kronoterm climate entities."""
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator

    async_add_entities([
        KronotermDHWClimate(parent_coordinator, main_coordinator),
        KronotermLoop1Climate(parent_coordinator, main_coordinator),
        KronotermLoop2Climate(parent_coordinator, main_coordinator),
    ])
    return True

class KronotermBaseClimate(CoordinatorEntity, ClimateEntity):
    """Base class for Kronoterm Climate Entities."""

    def __init__(self, parent_coordinator, coordinator, name, unique_id, min_temp, max_temp, page):
        """Initialize climate entity."""
        super().__init__(coordinator)
        self._parent_coordinator = parent_coordinator
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_hvac_modes = [HVACMode.HEAT]
        self._page = page  # API Page for this entity

        # ✅ Set step size to 0.1°C
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.1

    def _build_payload(self, new_temp):
        """Construct the payload for temperature updates."""
        return {
            "param_name": "circle_temp",
            "param_value": str(new_temp),
            "page": str(self._page)
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement for temperature."""
        return self.hass.config.units.temperature_unit

    @property
    def current_temperature(self):
        """Get the current temperature from HA sensor."""
        state = self.hass.states.get(self._current_temperature_sensor)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                return float(state.state.replace("°C", "").strip())
            except ValueError:
                _LOGGER.error(f"Invalid current temperature format: {state.state}")
                return None
        return None

    @property
    def target_temperature(self):
        """Get the desired temperature from HA sensor."""
        state = self.hass.states.get(self._desired_temperature_sensor)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                temp = float(state.state.replace("°C", "").strip())

                return temp
            except ValueError:
                _LOGGER.error(f"Invalid desired temperature format: {state.state}")
                return None
        return None

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature and ensure it is sent to the API."""
        new_temp = kwargs.get("temperature")
        if new_temp is None:
            _LOGGER.error(f"No temperature value provided for {self._attr_name}.")
            return

        _LOGGER.info(f"🔄 Setting {self._attr_name} temperature to: {new_temp}°C (Page: {self._page})")

        success = await self._parent_coordinator.async_set_temperature(self._page, round(new_temp, 1))
        if success:
            _LOGGER.info(f"✅ Successfully updated {self._attr_name} temperature to {new_temp}°C.")
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"❌ Failed to update {self._attr_name} temperature in API.")


# --- DHW Climate Entity ---
class KronotermDHWClimate(KronotermBaseClimate):
    """DHW Temperature Control."""
    def __init__(self, parent_coordinator, coordinator):
        super().__init__(parent_coordinator, coordinator, 
                         name="DHW Temperature", unique_id="dhw_climate",
                         min_temp=10, max_temp=90, page=9)
        self._current_temperature_sensor = "sensor.dhw_temperature"
        self._desired_temperature_sensor = "sensor.desired_dhw_temperature"

# --- Loop 1 Climate Entity ---
class KronotermLoop1Climate(KronotermBaseClimate):
    """Loop 1 Temperature Control."""
    def __init__(self, parent_coordinator, coordinator):
        super().__init__(parent_coordinator, coordinator, 
                         name="Loop 1 Temperature", unique_id="loop1_climate",
                         min_temp=10, max_temp=90, page=5)
        self._current_temperature_sensor = "sensor.loop_1_temperature"
        self._desired_temperature_sensor = "sensor.desired_loop_1_temperature"

# --- Loop 2 Climate Entity ---
class KronotermLoop2Climate(KronotermBaseClimate):
    """Loop 2 Temperature Control."""
    def __init__(self, parent_coordinator, coordinator):
        super().__init__(parent_coordinator, coordinator, 
                         name="Loop 2 Temperature", unique_id="loop2_climate",
                         min_temp=10, max_temp=90, page=6)
        self._current_temperature_sensor = "sensor.loop_2_thermostat_temperature"
        self._desired_temperature_sensor = "sensor.desired_loop_2_temperature"

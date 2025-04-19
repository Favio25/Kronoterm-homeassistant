import logging
from typing import Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

LOOP1_DESIRED_TEMP_ADDR = 2187

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up Kronoterm climate entities from config entry."""
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("No data found in hass.data for domain %s", DOMAIN)
        return False

    coordinator = data.get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s]", DOMAIN)
        return False

    # Create the climate entities
    entities = [
        KronotermDHWClimate(entry, coordinator),
        KronotermLoop1Climate(entry, coordinator, hass),
        KronotermLoop2Climate(entry, coordinator),
        KronotermReservoirClimate(entry, coordinator)
    ]

    # Add reservoir climate only if installed
    #if getattr(coordinator, "reservoir_installed", False):
    #    entities.append(KronotermReservoirClimate(entry, coordinator))
    #    _LOGGER.info("Reservoir climate entity added")
    #else:
    #    _LOGGER.info("Reservoir not installed, skipping Reservoir Climate Entity")

    async_add_entities(entities)
    return True


class KronotermBaseClimate(CoordinatorEntity, ClimateEntity):
    """Base class for Kronoterm Climate Entities."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        fallback_name: str,
        translation_key: str,
        unique_id_suffix: str,
        min_temp: float,
        max_temp: float,
        page: int,
        supports_cooling: bool = False
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)

        self._page = page
        self._attr_has_entity_name = True
        # Set a fallback name and use the proper translation key
        
        self._attr_translation_key = translation_key
        self._attr_entity_id = f"{DOMAIN}.{translation_key}"
        self._attr_name = fallback_name  # Fallback if no translation is found

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{unique_id_suffix}"

        # Show a single target-temperature control in HA's UI
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        # If hardware can do cooling, add COOL + OFF
        self._supports_cooling = supports_cooling
        if supports_cooling:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
            self._attr_hvac_mode = HVACMode.HEAT  # default
        else:
            self._attr_hvac_modes = [HVACMode.HEAT]
            self._attr_hvac_mode = HVACMode.HEAT

        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.1

        # Basic device info (manufacturer, model, etc.) from coordinator
        self._attr_device_info = coordinator.shared_device_info

        # If we eventually add a separate "mode_address," store it here
        self._mode_address = None

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit (°C or °F) set in Home Assistant."""
        return self.hass.config.units.temperature_unit

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC operation mode (HEAT, COOL, OFF)."""
        return self._attr_hvac_mode

    async def async_set_temperature(self, **kwargs) -> None:
        """
        Called by HA to set a new target temperature.
        We pass it to the coordinator's async_set_temperature(page, new_temp).
        """
        new_temp = kwargs.get("temperature")
        if new_temp is None:
            _LOGGER.error("%s: No temperature value provided", self.name)
            return

        # Validate range
        if new_temp < self._attr_min_temp or new_temp > self._attr_max_temp:
            _LOGGER.error(
                "%s: Temperature %.1f°C out of range (%.1f-%.1f)",
                self.name, new_temp, self._attr_min_temp, self._attr_max_temp
            )
            return

        new_temp_rounded = round(new_temp, 1)
        _LOGGER.info("%s: Setting temperature to %.1f°C (page=%d)",
                     self.name, new_temp_rounded, self._page)

        success = await self.coordinator.async_set_temperature(self._page, new_temp_rounded)
        if success:
            _LOGGER.info("%s: Successfully updated temperature to %.1f°C",
                         self.name, new_temp_rounded)
        else:
            _LOGGER.error("%s: Failed to update temperature", self.name)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Called by HA to set a new HVAC mode, e.g. COOL. Only works if hardware supports it."""
        if not self._supports_cooling:
            _LOGGER.warning("%s: This unit does not support changing HVAC mode", self.name)
            return

        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.warning("%s: Unsupported HVAC mode: %s", self.name, hvac_mode)
            return

        # Map hvac_mode to some integer we'd send to your coordinator
        mode_value = 0  # OFF
        if hvac_mode == HVACMode.HEAT:
            mode_value = 1
        elif hvac_mode == HVACMode.COOL:
            mode_value = 2

        _LOGGER.info("%s: Setting HVAC mode to %s (value=%d)",
                     self.name, hvac_mode, mode_value)

        success = True
        # If your coordinator has an async_set_hvac_mode method:
        if hasattr(self.coordinator, "async_set_hvac_mode"):
            success = await self.coordinator.async_set_hvac_mode(self._mode_address, mode_value)

        if success:
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()
            _LOGGER.info("%s: Successfully updated HVAC mode to %s", self.name, hvac_mode)
        else:
            _LOGGER.error("%s: Failed to update HVAC mode", self.name)


#
#   Domestic Hot Water (DHW)
#
class KronotermDHWClimate(KronotermBaseClimate):
    """Climate entity for domestic hot water (DHW)."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="DHW Temperature",
            translation_key="dhw_temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            page=9,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current measured DHW temperature from data['dhw'] if available."""
        dhw_data = self.coordinator.data.get("dhw")
        if not dhw_data:
            return None

        temps = dhw_data.get("TemperaturesAndConfig", {})
        raw = temps.get("tap_water_temp")  # e.g. "45.9"
        if not raw or raw in ("-60.0", "unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the user-set (desired) DHW temperature from data['dhw']['HeatingCircleData']['circle_temp']."""
        dhw_data = self.coordinator.data.get("dhw")
        if not dhw_data:
            return None

        circle_data = dhw_data.get("HeatingCircleData", {})
        raw = circle_data.get("circle_temp")  # e.g. "43.0"
        if not raw or raw in ("unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None


#
#   Loop 1
#
class KronotermLoop1Climate(KronotermBaseClimate):
    """Climate entity for heating Loop 1, with configurable target temp source."""

    def __init__(
        self, 
        entry: ConfigEntry, 
        coordinator: DataUpdateCoordinator,
        hass: HomeAssistant
    ):
        """Initialize the climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 1 Temperature",
            translation_key="loop_1_temperature",
            unique_id_suffix="loop1_climate",
            min_temp=10,
            max_temp=90,
            page=5,
        )
        # Store HomeAssistant instance
        self._hass = hass
        # Get temperature source from config entry options, default to "modbus"
        self._temp_source = entry.options.get("loop1_temp_source", "modbus")
        # Store the desired register address for target temperature
        self._desired_temp_address = LOOP1_DESIRED_TEMP_ADDR

        # Flag to set up event listener later
        self._listener_added = False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Now we can safely set up the event listener
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_loop1_source_changed",
                self._handle_source_changed
            )
        )
        self._listener_added = True

    @callback
    async def _handle_source_changed(self, event):
        """Handle event when temperature source is changed."""
        self._temp_source = event.data.get("source", "modbus")
        _LOGGER.info("%s: Temperature source changed to %s", self.name, self._temp_source)
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> float | None:
        """
        Return the current Loop 1 temperature.
        If the temperature source is "modbus", read from modbus address 2130
        and apply scaling (multiply by 0.1) if the value does not include a decimal point.
        Otherwise, read from JSON data.
        """
        if self._temp_source == "modbus":
            return self._read_modbus_value(2130, scale_if_no_decimal=True)
        else:
            loop1_data = self.coordinator.data.get("loop1")
            if not loop1_data:
                return None

            temps = loop1_data.get("TemperaturesAndConfig", {})
            raw = temps.get("heating_circle_1_temp")
            if not raw or raw in ("-60.0", "unknown", "unavailable"):
                return None

            try:
                return float(raw)
            except ValueError:
                return None

    @property
    def target_temperature(self) -> float | None:
        """
        Return the desired temperature based on the configured source:
        - "modbus": Read from Modbus register (address 2187)
        - "loop1_data": Read from loop1['HeatingCircleData']['circle_temp']
        """
        if self._temp_source == "modbus":
            return self._read_modbus_value(self._desired_temp_address)
        else:
            loop1_data = self.coordinator.data.get("loop1")
            if not loop1_data:
                return None

            circle_data = loop1_data.get("HeatingCircleData", {})
            raw = circle_data.get("circle_temp")
            if not raw or raw in ("unknown", "unavailable"):
                return None

            try:
                return float(raw)
            except ValueError:
                return None

    def _read_modbus_value(self, address: int, scale_if_no_decimal: bool = False) -> Optional[float]:
        """
        Helper to read a float from the 'main' ModbusReg data.
        If scale_if_no_decimal is True and the raw value doesn't contain a decimal point,
        multiply the value by 0.1.
        """
        main_data = self.coordinator.data.get("main", {})
        modbus_list = main_data.get("ModbusReg", [])
        if not modbus_list:
            return None

        reg = next((r for r in modbus_list if r.get("address") == address), None)
        if not reg:
            return None

        raw = reg.get("value")
        if not raw or raw in ("unknown", "unavailable"):
            return None

        if isinstance(raw, str):
            raw = raw.replace("°C", "").strip()
        # Use the string representation to check for a decimal point.
        raw_str = str(raw)
        try:
            value = float(raw)
            if scale_if_no_decimal and "." not in raw_str:
                value *= 0.1
            return value
        except ValueError:
            return None


#
#   Loop 2
#
class KronotermLoop2Climate(KronotermBaseClimate):
    """Climate entity for heating Loop 2."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 2 Temperature",
            translation_key="loop_2_temperature",
            unique_id_suffix="loop2_climate",
            min_temp=10,
            max_temp=90,
            page=6,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current Loop 2 temperature from data['loop2'] if available."""
        loop2_data = self.coordinator.data.get("loop2")
        if not loop2_data:
            return None

        temps = loop2_data.get("TemperaturesAndConfig", {})
        raw = temps.get("heating_circle_2_temp")  # e.g. "23.5"
        if not raw or raw in ("-60.0", "unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the set (desired) temperature from loop2['HeatingCircleData']['circle_temp']."""
        loop2_data = self.coordinator.data.get("loop2")
        if not loop2_data:
            return None

        circle_data = loop2_data.get("HeatingCircleData", {})
        raw = circle_data.get("circle_temp")  # e.g. "22.0"
        if not raw or raw in ("unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None


#
#   Reservoir
#
class KronotermReservoirClimate(KronotermBaseClimate):
    """Climate entity for reservoir temperature."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Reservoir Temperature",
            translation_key="reservoir_temperature",
            unique_id_suffix="reservoir_climate",
            min_temp=10,
            max_temp=90,
            page=4,  # used in async_set_temperature
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the reservoir's measured temperature from data['reservoir'] if available."""
        reservoir_data = self.coordinator.data.get("reservoir")
        if not reservoir_data:
            return None

        temps = reservoir_data.get("TemperaturesAndConfig", {})
        raw = temps.get("reservoir_temp")  # e.g. "38.0"
        if not raw or raw in ("-60.0", "unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        """
        Return the user-set reservoir target if the reservoir page uses the same
        'HeatingCircleData': {'circle_temp': ...} structure. Otherwise adapt.
        """
        reservoir_data = self.coordinator.data.get("reservoir")
        if not reservoir_data:
            return None

        circle_data = reservoir_data.get("HeatingCircleData", {})
        raw = circle_data.get("circle_temp")
        if not raw or raw in ("unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except ValueError:
            return None

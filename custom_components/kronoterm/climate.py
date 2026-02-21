import logging
from typing import Optional, Any

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

# Import the Modbus addresses needed for Loop 1
from .const import DOMAIN  # MODIFIED: Removed Loop1 specific addrs

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

    coordinator = data.get(entry.entry_id)
    _LOGGER.debug("Climate platform setup - Coordinator type: %s, Entry: %s", 
                   type(coordinator).__name__ if coordinator else "None", entry.entry_id)
    if not coordinator:
        _LOGGER.error("Coordinator not found in hass.data[%s] for entry %s", DOMAIN, entry.entry_id)
        return False

    # Check if Modbus coordinator
    is_modbus = hasattr(coordinator, 'register_map') and coordinator.register_map is not None
    
    entities = []
    
    if is_modbus:
        # Modbus-based climate entities
        _LOGGER.debug("Creating Modbus-based climate entities")
        
        # DHW (always available)
        if coordinator.tap_water_installed:
            entities.append(KronotermModbusDHWClimate(entry, coordinator))
            _LOGGER.debug("DHW installed, adding Modbus climate entity")
        
        # Loop 1
        if coordinator.loop1_installed:
            entities.append(KronotermModbusLoop1Climate(entry, coordinator))
            _LOGGER.debug("Loop 1 installed, adding Modbus climate entity")
        
        # Loop 2
        if coordinator.loop2_installed:
            entities.append(KronotermModbusLoop2Climate(entry, coordinator))
            _LOGGER.debug("Loop 2 installed, adding Modbus climate entity")
        
        # Loop 3
        if coordinator.loop3_installed:
            entities.append(KronotermModbusLoop3Climate(entry, coordinator))
            _LOGGER.debug("Loop 3 installed, adding Modbus climate entity")
        
        # Loop 4
        if coordinator.loop4_installed:
            entities.append(KronotermModbusLoop4Climate(entry, coordinator))
            _LOGGER.debug("Loop 4 installed, adding Modbus climate entity")
        
        # Reservoir
        if coordinator.reservoir_installed:
            entities.append(KronotermModbusReservoirClimate(entry, coordinator))
            _LOGGER.debug("Reservoir installed, adding Modbus climate entity")
    else:
        # Cloud API-based climate entities
        _LOGGER.info("Creating Cloud API-based climate entities")

        if getattr(coordinator, "system_type", "cloud") == "dhw":
            entities.append(KronotermDHWCloudClimate(entry, coordinator))
        else:
            entities.append(KronotermDHWClimate(entry, coordinator))

            if coordinator.loop1_installed:
                entities.append(KronotermLoop1Climate(entry, coordinator))

            if coordinator.loop2_installed:
                entities.append(KronotermLoop2Climate(entry, coordinator))

            if coordinator.loop3_installed:
                entities.append(KronotermLoop3Climate(entry, coordinator))

            if coordinator.loop4_installed:
                entities.append(KronotermLoop4Climate(entry, coordinator))

            if coordinator.reservoir_installed:
                entities.append(KronotermReservoirClimate(entry, coordinator))

    _LOGGER.debug("Created %d climate entities (%s mode)", 
                   len(entities), "Modbus" if is_modbus else "Cloud API")
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


# -------------------------------------------------------------------
# NEW BASE CLASS for simple JSON-based climate entities
# -------------------------------------------------------------------
class KronotermJsonClimate(KronotermBaseClimate):
    """Base for climate entities that read from a dedicated JSON data key."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        data_key: str,
        current_temp_json_key: str,
        target_temp_json_key: str = "circle_temp",
        **kwargs: Any
    ) -> None:
        """Initialize the JSON-based climate entity."""
        super().__init__(entry=entry, coordinator=coordinator, **kwargs)
        self._data_key = data_key
        self._current_temp_json_key = current_temp_json_key
        self._target_temp_json_key = target_temp_json_key

    def _get_modbus_value(self, address: int) -> Optional[float]:
        if not self.coordinator.data:
            return None
        modbus_list = self.coordinator.data.get("main", {}).get("ModbusReg", [])
        for reg in modbus_list:
            if reg.get("address") == address:
                return reg.get("value")
        return None


class KronotermLoopJsonClimate(KronotermJsonClimate):
    """Loop climate with preset modes mapped from loop mode register."""

    PRESET_MAP = {0: "off", 1: "on", 2: "auto"}
    PRESET_TO_VALUE = {v: k for k, v in PRESET_MAP.items()}

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        operation_mode_address: int,
        **kwargs: Any
    ) -> None:
        super().__init__(entry=entry, coordinator=coordinator, **kwargs)
        self._operation_mode_address = operation_mode_address
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        self._attr_preset_modes = list(self.PRESET_TO_VALUE.keys())
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_hvac_mode = HVACMode.HEAT
        self._last_heat_mode = 1

    def _get_mode_from_modbus(self) -> Optional[int]:
        modbus_list = (self.coordinator.data or {}).get("main", {}).get("ModbusReg", [])
        for reg in modbus_list:
            if reg.get("address") == self._operation_mode_address:
                try:
                    return int(float(reg.get("value")))
                except (TypeError, ValueError):
                    return None
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        val = self._get_mode_from_modbus()
        if val is None or val == 0:
            return HVACMode.OFF
        if val in (1, 2):
            self._last_heat_mode = val
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.warning("%s: Unsupported HVAC mode: %s", self.name, hvac_mode)
            return
        if hvac_mode == HVACMode.OFF:
            value = 0
        else:
            value = self._last_heat_mode or 1
        success = await self.coordinator.async_set_loop_mode_by_page(self._page, value)
        if not success:
            _LOGGER.error("Failed to set HVAC mode=%s (page=%s)", hvac_mode, self._page)
        else:
            await self.coordinator.async_request_refresh()

    @property
    def preset_mode(self) -> str | None:
        val = self._get_mode_from_modbus()
        if val is None:
            return None
        return self.PRESET_MAP.get(val)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        value = self.PRESET_TO_VALUE.get(preset_mode)
        if value is None:
            _LOGGER.warning("Unknown loop preset_mode: %s", preset_mode)
            return
        success = await self.coordinator.async_set_loop_mode_by_page(self._page, value)
        if not success:
            _LOGGER.error("Failed to set loop preset_mode=%s (page=%s)", preset_mode, self._page)
        else:
            if value in (1, 2):
                self._last_heat_mode = value
            await self.coordinator.async_request_refresh()

    @property
    def _json_data(self) -> dict | None:
        """Helper to get the specific data blob for this entity."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._data_key)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature from the dedicated JSON data blob."""
        data = self._json_data
        if not data:
            return None

        temps = data.get("TemperaturesAndConfig", {})
        raw = temps.get(self._current_temp_json_key)
        if not raw or raw in ("-60.0", "unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature from the dedicated JSON data blob."""
        data = self._json_data
        if not data:
            return None

        circle_data = data.get("HeatingCircleData", {})
        raw = circle_data.get(self._target_temp_json_key)
        if not raw or raw in ("unknown", "unavailable"):
            return None

        try:
            return float(raw)
        except (ValueError, TypeError):
            return None


#
#   Domestic Hot Water (DHW) - Refactored
#
class KronotermDHWCloudClimate(KronotermBaseClimate):
    """DHW climate entity for Water Cloud (BasicData fields)."""

    PRESET_MAP = {
        0: "off",
        1: "normal",
        2: "eco",
        3: "comfort",
        4: "lux_plus",
        5: "ext_source",
        6: "pv",
        8: "f1",
        9: "f2",
        10: "f3",
    }
    PRESET_TO_VALUE = {v: k for k, v in PRESET_MAP.items()}

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="DHW Temperature",
            translation_key="dhw_temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            page=1,
        )
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        self._attr_preset_modes = list(self.PRESET_TO_VALUE.keys())

    @property
    def current_temperature(self) -> float | None:
        data = (self.coordinator.data or {}).get("main", {})
        raw = data.get("GlobalOverview", {}).get("boiler_temp")
        if raw is None:
            raw = data.get("BasicData", {}).get("boiler_calc_temp")
        if raw is None:
            raw = data.get("BasicData", {}).get("boiler_temp")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        data = (self.coordinator.data or {}).get("main", {})
        raw = data.get("BasicData", {}).get("boiler_setpoint")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def preset_mode(self) -> str | None:
        data = (self.coordinator.data or {}).get("main", {})
        raw = data.get("BasicData", {}).get("default_mode")
        try:
            return self.PRESET_MAP.get(int(raw))
        except (TypeError, ValueError):
            return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        value = self.PRESET_TO_VALUE.get(preset_mode)
        if value is None:
            _LOGGER.warning("Unknown DHW preset_mode: %s", preset_mode)
            return
        if hasattr(self.coordinator, "async_set_dhw_default_mode"):
            await self.coordinator.async_set_dhw_default_mode(value)
        else:
            _LOGGER.error("Coordinator missing async_set_dhw_default_mode")


class KronotermDHWClimate(KronotermJsonClimate):
    """Climate entity for domestic hot water (DHW)."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="dhw",
            current_temp_json_key="tap_water_temp",
            # target_temp_json_key defaults to "circle_temp", which is correct
            fallback_name="DHW Temperature",
            translation_key="dhw_temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            page=9,
        )

    @property
    def current_temperature(self) -> float | None:
        # Prefer ModbusReg address 2102 for cloud mode
        raw = self._get_modbus_value(2102)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
        return super().current_temperature

    @property
    def target_temperature(self) -> float | None:
        raw = self._get_modbus_value(2023)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
        return super().target_temperature


# --- MODIFIED: START OF Loop 1 REPLACEMENT ---
#
#   Loop 1 (Refactored to match other loops)
#
class KronotermLoop1Climate(KronotermLoopJsonClimate):
    """Climate entity for heating Loop 1."""

    def __init__(
        self, 
        entry: ConfigEntry, 
        coordinator: DataUpdateCoordinator
    ):
        """Initialize the climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="loop1",
            current_temp_json_key="heating_circle_1_temp",
            fallback_name="Loop 1 Temperature",
            translation_key="loop_1_temperature",
            unique_id_suffix="loop1_climate",
            min_temp=10,
            max_temp=90,
            page=5,
            operation_mode_address=2042,
        )
# --- MODIFIED: END OF Loop 1 REPLACEMENT ---


#
#   Loop 2 - Refactored
#
class KronotermLoop2Climate(KronotermLoopJsonClimate):
    """Climate entity for heating Loop 2."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="loop2",
            current_temp_json_key="heating_circle_2_temp",
            fallback_name="Loop 2 Temperature",
            translation_key="loop_2_temperature",
            unique_id_suffix="loop2_climate",
            min_temp=10,
            max_temp=90,
            page=6,
            operation_mode_address=2052,
        )


# --- ADDED LOOP 3 ---
#
#   Loop 3
#
class KronotermLoop3Climate(KronotermLoopJsonClimate):
    """Climate entity for heating Loop 3."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="loop3",
            current_temp_json_key="heating_circle_3_temp",
            fallback_name="Loop 3 Temperature",
            translation_key="loop_3_temperature",
            unique_id_suffix="loop3_climate",
            min_temp=10,
            max_temp=90,
            page=7,
            operation_mode_address=2062,
        )


# --- ADDED LOOP 4 ---
#
#   Loop 4
#
class KronotermLoop4Climate(KronotermLoopJsonClimate):
    """Climate entity for heating Loop 4."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="loop4",
            current_temp_json_key="heating_circle_4_temp",
            fallback_name="Loop 4 Temperature",
            translation_key="loop_4_temperature",
            unique_id_suffix="loop4_climate",
            min_temp=10,
            max_temp=90,
            page=8,
            operation_mode_address=2072,
        )


#
#   Reservoir - Refactored
#
class KronotermReservoirClimate(KronotermJsonClimate):
    """Climate entity for reservoir temperature."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            data_key="reservoir",
            current_temp_json_key="reservoir_temp",
            # target_temp_json_key defaults to "circle_temp", which is correct
            fallback_name="Reservoir Temperature",
            translation_key="reservoir_temperature",
            unique_id_suffix="reservoir_climate",
            min_temp=10,
            max_temp=90,
            page=4,
        )

    @property
    def current_temperature(self) -> float | None:
        raw = self._get_modbus_value(2101)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
        return super().current_temperature

    @property
    def target_temperature(self) -> float | None:
        raw = self._get_modbus_value(2034)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
        return super().target_temperature


# ===================================================================
# MODBUS-BASED CLIMATE ENTITIES
# ===================================================================

class KronotermModbusBaseClimate(CoordinatorEntity, ClimateEntity):
    """Base class for Modbus-based Kronoterm Climate Entities."""

    PRESET_MAP = {0: "off", 1: "on", 2: "auto"}
    PRESET_TO_VALUE = {v: k for k, v in PRESET_MAP.items()}

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        fallback_name: str,
        translation_key: str,
        unique_id_suffix: str,
        min_temp: float,
        max_temp: float,
        current_temp_address: int,
        thermostat_temp_address: int | None,
        target_temp_address: int,
        write_temp_address: int,
        operation_mode_address: int,
        supports_cooling: bool = False,
        enable_preset: bool = False,
    ) -> None:
        """Initialize the Modbus climate entity."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        self._attr_translation_key = translation_key
        self._attr_name = fallback_name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{unique_id_suffix}"

        self._enable_preset = enable_preset
        if enable_preset:
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(self.PRESET_TO_VALUE.keys())
        else:
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        # All zones support OFF mode via operation_mode register
        self._supports_cooling = supports_cooling
        if supports_cooling:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
        else:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.1

        self._attr_device_info = coordinator.shared_device_info

        # Register addresses
        self._current_temp_address = current_temp_address
        self._thermostat_temp_address = thermostat_temp_address
        self._target_temp_address = target_temp_address
        self._write_temp_address = write_temp_address
        self._operation_mode_address = operation_mode_address
        
        # Remember last HEAT mode (1=Normal, 2=Schedule) to restore when turning back ON
        self._last_heat_mode = 1  # Default to Normal mode

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        return self.hass.config.units.temperature_unit

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC operation mode based on operation_mode register.
        
        Also checks target temperature for dependency-based OFF states.
        
        Operation mode values:
        0 = Izklop (OFF)
        1 = Normalni režim (Normal/HEAT)
        2 = Delovanje po urniku (Schedule/HEAT)
        """
        operation_mode = self._get_register_value(self._operation_mode_address)
        
        if operation_mode is None:
            return HVACMode.OFF
        
        # Check 1: Proper OFF state
        if operation_mode == 0:
            return HVACMode.OFF
        
        # Check 2: Dependency-based OFF (target temp shows 500)
        # This catches cases like: Reservoir functionally OFF when Loop 1 is OFF
        target_temp = self._get_register_value(self._target_temp_address)
        if target_temp is not None and target_temp >= 500.0:
            return HVACMode.OFF
        
        # Zone is ON
        # Remember the last non-OFF mode to restore it later
        self._last_heat_mode = operation_mode
        return HVACMode.HEAT

    def _get_register_value(self, address: int) -> float | None:
        """Helper to get register value from coordinator data."""
        if not self.coordinator.data:
            return None
        
        # Data is in format: {"main": {"ModbusReg": [...]}}
        modbus_list = self.coordinator.data.get("main", {}).get("ModbusReg", [])
        for reg in modbus_list:
            if reg.get("address") == address:
                return reg.get("value")
        
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature (prefer thermostat, fallback to loop)."""
        # Try thermostat temperature first
        if self._thermostat_temp_address:
            thermostat_temp = self._get_register_value(self._thermostat_temp_address)
            if thermostat_temp is not None and thermostat_temp != -60.0 and thermostat_temp != 0.0:
                return thermostat_temp

        # Fall back to loop temperature
        loop_temp = self._get_register_value(self._current_temp_address)
        if loop_temp is not None and loop_temp != -60.0:
            return loop_temp

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature.
        
        Returns None (unavailable) when:
        - Zone is OFF (operation_mode = 0)
        - Value is 500+ (OFF value from installation-specific dependencies)
        - Value is -60.0 (sensor error)
        """
        # Check if zone is OFF (proper state)
        operation_mode = self._get_register_value(self._operation_mode_address)
        if operation_mode == 0:
            return None
        
        # Get target temperature
        temp = self._get_register_value(self._target_temp_address)
        
        # Filter invalid values
        if temp is None:
            return None
        if temp == -60.0:  # Sensor error
            return None
        if temp >= 500.0:  # OFF value (5000 raw) from dependencies
            return None
        
        return temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
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
        _LOGGER.info("%s: Setting temperature to %.1f°C (address=%d)",
                     self.name, new_temp_rounded, self._write_temp_address)

        success = await self.coordinator.async_write_register(
            self._write_temp_address, new_temp_rounded
        )
        
        if success:
            _LOGGER.info("%s: Successfully updated temperature to %.1f°C",
                         self.name, new_temp_rounded)
            # Request immediate refresh
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("%s: Failed to update temperature", self.name)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode (OFF or HEAT) by writing to operation_mode register.
        
        When turning back to HEAT, restores the previous mode (Normal or Schedule).
        
        Operation mode values:
        0 = Izklop (OFF)
        1 = Normalni režim (Normal/HEAT)
        2 = Delovanje po urniku (Schedule/HEAT)
        """
        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.warning("%s: Unsupported HVAC mode: %s", self.name, hvac_mode)
            return

        # Map HVAC mode to operation mode value
        if hvac_mode == HVACMode.OFF:
            operation_mode_value = 0
        elif hvac_mode == HVACMode.HEAT:
            # Restore previous mode (Normal=1 or Schedule=2)
            operation_mode_value = self._last_heat_mode
            _LOGGER.debug("%s: Restoring previous HEAT mode: %d", self.name, operation_mode_value)
        elif hvac_mode == HVACMode.COOL:
            operation_mode_value = 1  # For future cooling support
        else:
            _LOGGER.error("%s: Unknown HVAC mode: %s", self.name, hvac_mode)
            return

        _LOGGER.info("%s: Setting HVAC mode to %s (writing %d to address %d)",
                     self.name, hvac_mode, operation_mode_value, self._operation_mode_address)

        success = await self.coordinator.async_write_register(
            self._operation_mode_address, operation_mode_value
        )
        
        if success:
            _LOGGER.info("%s: Successfully updated HVAC mode to %s",
                         self.name, hvac_mode)
            # Request immediate refresh
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("%s: Failed to update HVAC mode", self.name)

    @property
    def preset_mode(self) -> str | None:
        if not self._enable_preset:
            return None
        operation_mode = self._get_register_value(self._operation_mode_address)
        if operation_mode is None:
            return None
        return self.PRESET_MAP.get(int(operation_mode))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if not self._enable_preset:
            return
        value = self.PRESET_TO_VALUE.get(preset_mode)
        if value is None:
            _LOGGER.warning("Unknown preset_mode: %s", preset_mode)
            return
        success = await self.coordinator.async_write_register(
            self._operation_mode_address, value
        )
        if success:
            await self.coordinator.async_request_refresh()


class KronotermModbusDHWClimate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for domestic hot water (DHW)."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="DHW Temperature",
            translation_key="dhw_temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2102,  # dhw_temperature
            thermostat_temp_address=None,  # DHW has no thermostat
            target_temp_address=2024,  # dhw_current_setpoint
            write_temp_address=2023,  # dhw_setpoint
            operation_mode_address=2026,  # dhw_operation_mode
        )


class KronotermModbusLoop1Climate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for heating Loop 1."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 1 Temperature",
            translation_key="loop_1_temperature",
            unique_id_suffix="loop1_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2130,  # loop_1_temperature
            thermostat_temp_address=2160,  # loop_1_thermostat_temperature
            target_temp_address=2191,  # loop_1_room_current_setpoint
            write_temp_address=2187,  # loop_1_room_setpoint
            operation_mode_address=2042,  # loop_1_operation_mode
            enable_preset=True,
        )


class KronotermModbusLoop2Climate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for heating Loop 2."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 2 Temperature",
            translation_key="loop_2_temperature",
            unique_id_suffix="loop2_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2110,  # loop_2_temperature
            thermostat_temp_address=2161,  # loop_2_thermostat_temperature
            target_temp_address=2051,  # loop_2_room_current_setpoint
            write_temp_address=2049,  # loop_2_setpoint
            operation_mode_address=2052,  # loop_2_operation_mode
            enable_preset=True,
        )


class KronotermModbusLoop3Climate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for heating Loop 3."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 3 Temperature",
            translation_key="loop_3_temperature",
            unique_id_suffix="loop3_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2111,  # loop_3_temperature
            thermostat_temp_address=2162,  # loop_3_thermostat_temperature
            target_temp_address=2061,  # loop_3_room_current_setpoint
            write_temp_address=2059,  # loop_3_setpoint
            operation_mode_address=2062,  # loop_3_operation_mode
            enable_preset=True,
        )


class KronotermModbusLoop4Climate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for heating Loop 4."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Loop 4 Temperature",
            translation_key="loop_4_temperature",
            unique_id_suffix="loop4_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2112,  # loop_4_temperature
            thermostat_temp_address=2163,  # loop_4_thermostat_temperature
            target_temp_address=2071,  # loop_4_room_current_setpoint
            write_temp_address=2069,  # loop_4_setpoint
            operation_mode_address=2072,  # loop_4_operation_mode
            enable_preset=True,
        )


class KronotermModbusReservoirClimate(KronotermModbusBaseClimate):
    """Modbus-based climate entity for reservoir."""

    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            fallback_name="Reservoir Temperature",
            translation_key="reservoir_temperature",
            unique_id_suffix="reservoir_climate",
            min_temp=10,
            max_temp=90,
            current_temp_address=2101,  # return_temperature (used as reservoir temp)
            thermostat_temp_address=None,  # No thermostat for reservoir
            target_temp_address=2034,  # reservoir_current_setpoint
            write_temp_address=2305,  # solar_reservoir_setpoint
            operation_mode_address=2035,  # reservoir_operation_mode
        )
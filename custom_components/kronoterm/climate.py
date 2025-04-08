import logging
from typing import Dict, List, Optional, Union, Any, cast

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

from .const import (
    DOMAIN,
    # DHW Modbus addresses
    DHW_CURRENT_TEMP_ADDR,
    DHW_DESIRED_TEMP_ADDR,
    # Loop 1 Modbus addresses
    LOOP1_CURRENT_BASIC_ADDR,
    LOOP1_CURRENT_THERM_ADDR,
    LOOP1_DESIRED_TEMP_ADDR,
    LOOP1_THERMOSTAT_FLAG_ADDR,
    # Loop 2 Modbus addresses
    LOOP2_CURRENT_BASIC_ADDR,
    LOOP2_CURRENT_THERM_ADDR,
    LOOP2_DESIRED_TEMP_ADDR,
    LOOP2_THERMOSTAT_FLAG_ADDR,
    # Reservoir address
    RESERVOIR_TEMP_ADDR,
)

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
        KronotermLoop1Climate(entry, coordinator),
        KronotermLoop2Climate(entry, coordinator),
    ]

    # Optionally add reservoir climate if installed
    if getattr(coordinator, "reservoir_installed", False):
        entities.append(KronotermReservoirClimate(entry, coordinator))
        _LOGGER.info("Reservoir climate entity added")
    else:
        _LOGGER.info("Reservoir not installed, skipping Reservoir Climate Entity")

    async_add_entities(entities)
    return True


class KronotermBaseClimate(CoordinatorEntity, ClimateEntity):
    """Base class for Kronoterm Climate Entities."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id_suffix: str,
        min_temp: float,
        max_temp: float,
        page: int,
    ) -> None:
        """Initialize the climate entity.
        
        Args:
            entry: The config entry
            coordinator: The data update coordinator
            name: The entity name
            unique_id_suffix: Suffix for the entity unique ID
            min_temp: Minimum allowed temperature
            max_temp: Maximum allowed temperature
            page: The Kronoterm "page" for temperature updates
        """
        super().__init__(coordinator)

        self._page = page
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{unique_id_suffix}"
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_hvac_modes = [HVACMode.HEAT]
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.1

        # Shared device info from coordinator
        self._attr_device_info = coordinator.shared_device_info

        # Will be set by subclasses
        self._current_temp_address: Optional[int] = None
        self._desired_temp_address: Optional[int] = None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self.hass.config.units.temperature_unit

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._read_modbus_temp(self._current_temp_address)

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature."""
        return self._read_modbus_temp(self._desired_temp_address)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        return HVACMode.HEAT

    def _read_modbus_temp(self, address: Optional[int]) -> Optional[float]:
        """
        Read a temperature value from modbus registers.
        
        Args:
            address: The modbus address to read from
            
        Returns:
            The temperature value as a float, or None if not available
        """
        if not address:
            return None

        try:
            data = self.coordinator.data or {}
            main_data = data.get("main", {})
            if not main_data:
                _LOGGER.debug("%s: No main data available", self.name)
                return None
                
            modbus_list = main_data.get("ModbusReg", [])
            if not modbus_list:
                _LOGGER.debug("%s: No ModbusReg data available", self.name)
                return None

            reg = next((r for r in modbus_list if r.get("address") == address), None)
            if not reg:
                _LOGGER.debug("%s: Register %d not found", self.name, address)
                return None

            raw_value = reg.get("value")
            if not raw_value or raw_value in ("unknown", "unavailable"):
                return None

            if isinstance(raw_value, str):
                raw_value = raw_value.replace("°C", "").strip()

            return float(raw_value)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("%s: Error reading modbus value at %d: %s", self.name, address, e)
            return None
        except Exception as e:
            _LOGGER.error("%s: Unexpected error reading modbus value: %s", self.name, e)
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        """
        Set a new target temperature for this climate entity.
        
        Args:
            **kwargs: Keyword arguments from HA climate service call.
                     Contains 'temperature' key with the new target value.
        """
        new_temp = kwargs.get("temperature")
        if new_temp is None:
            _LOGGER.error("%s: No temperature value provided", self.name)
            return

        # Validate temperature range
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


class KronotermDHWClimate(KronotermBaseClimate):
    """Climate entity for domestic hot water (DHW)."""
    
    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        """Initialize the DHW climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            name="DHW Temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            page=9,
        )
        self._current_temp_address = DHW_CURRENT_TEMP_ADDR
        self._desired_temp_address = DHW_DESIRED_TEMP_ADDR


class KronotermLoopClimate(KronotermBaseClimate):
    """Base class for heating loop climate entities with switchable address."""
    
    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id_suffix: str,
        page: int,
        basic_addr: int,
        therm_addr: int,
        desired_addr: int,
        flag_addr: int,
        use_scaling: bool = False
    ) -> None:
        """Initialize loop climate entity.
        
        Args:
            entry: Config entry
            coordinator: Data coordinator
            name: Entity name
            unique_id_suffix: Unique ID suffix
            page: Control page number
            basic_addr: Address for basic temperature reading
            therm_addr: Address for thermostat temperature reading
            desired_addr: Address for desired temperature
            flag_addr: Address for thermostat mode flag
            use_scaling: Whether to apply scaling to the basic temperature
        """
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            name=name,
            unique_id_suffix=unique_id_suffix,
            min_temp=10,
            max_temp=90,
            page=page,
        )
        self._basic_addr = basic_addr
        self._therm_addr = therm_addr
        self._flag_addr = flag_addr
        self._desired_temp_address = desired_addr
        self._current_temp_address = basic_addr  # Default
        self._use_scaling = use_scaling
        
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()
        self._handle_coordinator_update()

    @property
    def current_temperature(self) -> Optional[float]:
        """Return current temperature with scaling if necessary."""
        raw_temp = self._read_modbus_temp(self._current_temp_address)
        if raw_temp is not None and self._use_scaling and self._current_temp_address == self._basic_addr:
            return round(raw_temp * 0.1, 1)
        return raw_temp

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            data = self.coordinator.data or {}
            main_data = data.get("main", {})
            if not main_data:
                _LOGGER.debug("%s: No main data for address selection", self.name)
                super()._handle_coordinator_update()
                return
                
            modbus_list = main_data.get("ModbusReg", [])
            if not modbus_list:
                _LOGGER.debug("%s: No ModbusReg data for address selection", self.name)
                super()._handle_coordinator_update()
                return

            # Find the flag register value
            flag_reg = next((r for r in modbus_list if r.get("address") == self._flag_addr), None)
            
            # Default to basic address
            new_address = self._basic_addr
            
            # If flag is set, use thermostat address
            if flag_reg and flag_reg.get("value", 0) != 0:
                new_address = self._therm_addr

            # If address changed, update and notify
            if self._current_temp_address != new_address:
                _LOGGER.info("%s: switching current temp address to %s", self.name, new_address)
                self._current_temp_address = new_address
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("%s: Error updating temperature address: %s", self.name, e)
            
        super()._handle_coordinator_update()


class KronotermLoop1Climate(KronotermLoopClimate):
    """Climate entity for heating Loop 1."""
    
    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        """Initialize Loop 1 climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            name="Loop 1 Temperature",
            unique_id_suffix="loop1_climate",
            page=5,
            basic_addr=LOOP1_CURRENT_BASIC_ADDR,
            therm_addr=LOOP1_CURRENT_THERM_ADDR,
            desired_addr=LOOP1_DESIRED_TEMP_ADDR,
            flag_addr=LOOP1_THERMOSTAT_FLAG_ADDR,
            use_scaling=True
        )


class KronotermLoop2Climate(KronotermLoopClimate):
    """Climate entity for heating Loop 2."""
    
    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        """Initialize Loop 2 climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            name="Loop 2 Temperature",
            unique_id_suffix="loop2_climate",
            page=6,
            basic_addr=LOOP2_CURRENT_BASIC_ADDR,
            therm_addr=LOOP2_CURRENT_THERM_ADDR,
            desired_addr=LOOP2_DESIRED_TEMP_ADDR,
            flag_addr=LOOP2_THERMOSTAT_FLAG_ADDR,
            use_scaling=False
        )


class KronotermReservoirClimate(KronotermBaseClimate):
    """Climate entity for reservoir temperature."""
    
    def __init__(self, entry: ConfigEntry, coordinator: DataUpdateCoordinator):
        """Initialize reservoir climate entity."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            name="Reservoir Temperature",
            unique_id_suffix="reservoir_climate",
            min_temp=10,
            max_temp=90,
            page=4,
        )
        self._current_temp_address = RESERVOIR_TEMP_ADDR
        self._desired_temp_address = RESERVOIR_TEMP_ADDR
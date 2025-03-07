import logging
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

_LOGGER = logging.getLogger(__name__)

# -----------------------------
# Modbus addresses for climates
# -----------------------------
# DHW
DHW_CURRENT_TEMP_ADDR = 2102      # "DHW Temperature"
DHW_DESIRED_TEMP_ADDR = 2023      # "Desired DHW Temperature"

# Loop 1
LOOP1_CURRENT_BASIC_ADDR = 2130   # "Loop 1 Temperature" (no thermostat)
LOOP1_CURRENT_THERM_ADDR = 2160   # "Loop 1 Thermostat Temperature" (thermostat installed)
LOOP1_DESIRED_TEMP_ADDR = 2187    # "Desired Loop 1 Temperature"
LOOP1_THERMOSTAT_FLAG_ADDR = 2192 # If !=0 => thermostat installed

# Loop 2
LOOP2_CURRENT_BASIC_ADDR = 2110   # "Loop 2 Temperature"
LOOP2_CURRENT_THERM_ADDR = 2161   # "Loop 2 Thermostat Temperature"
LOOP2_DESIRED_TEMP_ADDR = 2049    # "Desired Loop 2 Temperature"
LOOP2_THERMOSTAT_FLAG_ADDR = 2193 # If !=0 => thermostat installed


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator

    entities = [
        KronotermDHWClimate(entry, parent_coordinator, main_coordinator),
        KronotermLoop1Climate(entry, parent_coordinator, main_coordinator),
        KronotermLoop2Climate(entry, parent_coordinator, main_coordinator),
    ]
    
    # Only add the reservoir climate entity if the reservoir is installed.
    if getattr(parent_coordinator, "reservoir_installed", False):
        entities.append(KronotermReservoirClimate(entry, parent_coordinator, main_coordinator))
    else:
        _LOGGER.info("Reservoir not installed, skipping Reservoir Climate Entity.")
    
    async_add_entities(entities)
    return True



class KronotermBaseClimate(CoordinatorEntity, ClimateEntity):
    """
    Base class for Kronoterm Climate Entities that reads directly from ModbusReg.
    Subclasses provide the addresses for current/desired temps (and dynamic logic if needed).
    """

    def __init__(
        self,
        entry: ConfigEntry,
        parent_coordinator,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id_suffix: str,
        min_temp: float,
        max_temp: float,
        page: int,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)

        self._parent_coordinator = parent_coordinator
        self._page = page  # The Kronoterm "page" for temperature updates

        # Basic climate entity properties
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{unique_id_suffix}"
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_hvac_modes = [HVACMode.HEAT]
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.1

        # Attach the same device info as other Kronoterm entities
        self._attr_device_info = parent_coordinator.shared_device_info

        # Addresses for current & desired temps (set by child classes)
        self._current_temp_address: int | None = None
        self._desired_temp_address: int | None = None

    @property
    def temperature_unit(self) -> str:
        """Return the system's configured temperature unit (°C or °F)."""
        return self.hass.config.units.temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature by reading directly from ModbusReg."""
        return self._read_modbus_temp(self._current_temp_address)

    @property
    def target_temperature(self) -> float | None:
        """Return the target (desired) temperature by reading from ModbusReg."""
        return self._read_modbus_temp(self._desired_temp_address)

    @property
    def hvac_mode(self) -> HVACMode:
        """We only support heating in this example."""
        return HVACMode.HEAT

    def _read_modbus_temp(self, address: int | None) -> float | None:
        """Fetch a numeric temperature from the coordinator data at the given modbus address."""
        if not address:
            return None
        modbus_data = self.coordinator.data.get("ModbusReg", [])
        reg = next((r for r in modbus_data if r["address"] == address), None)
        if not reg:
            return None

        raw_value = reg.get("value")
        if not raw_value or raw_value in ("unknown", "unavailable"):
            return None

        # Sometimes the value might be a string like "45.0 °C"
        if isinstance(raw_value, str):
            raw_value = raw_value.replace("°C", "").strip()

        try:
            return float(raw_value)
        except (ValueError, TypeError):
            return None

    async def async_set_temperature(self, **kwargs) -> None:
        """
        Handle setting a new target temperature by calling the Kronoterm API.
        If successful, request a refresh from the coordinator.
        """
        new_temp = kwargs.get("temperature")
        if new_temp is None:
            _LOGGER.error("No temperature value provided for %s.", self._attr_name)
            return

        new_temp_rounded = round(new_temp, 1)
        _LOGGER.info(
            "🔄 Setting %s temperature to %s°C (Page: %s)",
            self._attr_name,
            new_temp_rounded,
            self._page,
        )

        success = await self._parent_coordinator.async_set_temperature(
            self._page,
            new_temp_rounded
        )
        if success:
            _LOGGER.info(
                "✅ Successfully updated %s temperature to %s°C.",
                self._attr_name,
                new_temp_rounded,
            )
            # Force a data refresh to show updated values quickly
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ Failed to update %s temperature in Kronoterm API.", self._attr_name)


class KronotermDHWClimate(KronotermBaseClimate):
    """
    Climate entity for DHW (domestic hot water), reading from Modbus directly:
      - current = address 2102
      - desired = address 2023
      - page = 9
    """

    def __init__(self, entry, parent_coordinator, coordinator):
        super().__init__(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=coordinator,
            name="DHW Temperature",
            unique_id_suffix="dhw_climate",
            min_temp=10,
            max_temp=90,
            page=9,
        )
        self._current_temp_address = DHW_CURRENT_TEMP_ADDR
        self._desired_temp_address = DHW_DESIRED_TEMP_ADDR


class KronotermLoop1Climate(KronotermBaseClimate):
    """
    Climate entity for Loop 1, choosing between:
      - Loop 1 Temperature (address 2130) if thermostat is NOT installed (Modbus 2192 == 0)
      - Loop 1 Thermostat Temperature (address 2160) if thermostat is installed (Modbus 2192 != 0)
    Desired temperature = address 2187, page=5
    """

    def __init__(self, entry, parent_coordinator, coordinator):
        super().__init__(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=coordinator,
            name="Loop 1 Temperature",
            unique_id_suffix="loop1_climate",
            min_temp=10,
            max_temp=90,
            page=5,
        )
        # Desired always the same address
        self._desired_temp_address = LOOP1_DESIRED_TEMP_ADDR

    async def async_added_to_hass(self) -> None:
        """Once added, determine the correct current temp address."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Choose which address to use for current temperature based on register 2192."""
        data = self.coordinator.data
        if not data:
            # No data yet; default to basic sensor
            if not self._current_temp_address:
                self._current_temp_address = LOOP1_CURRENT_BASIC_ADDR
            return

        modbus_data = data.get("ModbusReg", [])
        reg_2192 = next((r for r in modbus_data if r["address"] == LOOP1_THERMOSTAT_FLAG_ADDR), None)

        new_address = LOOP1_CURRENT_BASIC_ADDR
        if reg_2192 and reg_2192.get("value", 0) != 0:
            new_address = LOOP1_CURRENT_THERM_ADDR

        if self._current_temp_address != new_address:
            _LOGGER.info(
                "Loop 1 climate: switching current temp address to %s",
                new_address
            )
            self._current_temp_address = new_address
            self.async_write_ha_state()

        # Call parent last
        super()._handle_coordinator_update()


class KronotermLoop2Climate(KronotermBaseClimate):
    """
    Climate entity for Loop 2, choosing between:
      - Loop 2 Temperature (address 2110) if thermostat is NOT installed (Modbus 2193 == 0)
      - Loop 2 Thermostat Temperature (address 2161) if thermostat is installed (Modbus 2193 != 0)
    Desired temperature = address 2049, page=6
    """

    def __init__(self, entry, parent_coordinator, coordinator):
        super().__init__(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=coordinator,
            name="Loop 2 Temperature",
            unique_id_suffix="loop2_climate",
            min_temp=10,
            max_temp=90,
            page=6,
        )
        # Desired always the same address
        self._desired_temp_address = LOOP2_DESIRED_TEMP_ADDR

    async def async_added_to_hass(self) -> None:
        """Initialize sensor choice once entity is added to HA."""
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Check address 2193 in Modbus to decide which current temp address to use."""
        data = self.coordinator.data
        if not data:
            if not self._current_temp_address:
                self._current_temp_address = LOOP2_CURRENT_BASIC_ADDR
            return

        modbus_data = data.get("ModbusReg", [])
        reg_2193 = next((r for r in modbus_data if r["address"] == LOOP2_THERMOSTAT_FLAG_ADDR), None)

        new_address = LOOP2_CURRENT_BASIC_ADDR
        if reg_2193 and reg_2193.get("value", 0) != 0:
            new_address = LOOP2_CURRENT_THERM_ADDR

        if self._current_temp_address != new_address:
            _LOGGER.info(
                "Loop 2 climate: switching current temp address to %s",
                new_address
            )
            self._current_temp_address = new_address
            self.async_write_ha_state()

        super()._handle_coordinator_update()

class KronotermReservoirClimate(KronotermBaseClimate):
    """
    Climate entity for controlling the Reservoir Temperature.
    Uses Modbus register 2101 for both current and desired temperatures.
    Sends control commands using page 4.
    """
    def __init__(self, entry, parent_coordinator, coordinator):
        super().__init__(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=coordinator,
            name="Reservoir Temperature",
            unique_id_suffix="reservoir_climate",
            min_temp=10,  # Adjust as needed
            max_temp=90,
            page=4,       # This tells the coordinator to use the reservoir control query
        )
        self._current_temp_address = 2101
        self._desired_temp_address = 2101



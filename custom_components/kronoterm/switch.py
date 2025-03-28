import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the Kronoterm switch platform via config entry."""
    # Get the Kronoterm coordinator wrapper from hass.data
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator

    # Instantiate our single switch entity (or create a list if needed)
    pump_switch_entity = KronotermHeatPumpSwitch(
        entry,
        parent_coordinator,
        main_coordinator,
    )
    dhw_circulation_switch_entity = DHWCirculationSwitch(
        entry,
        parent_coordinator,
        main_coordinator,
    )

    
    async_add_entities([pump_switch_entity, dhw_circulation_switch_entity])
    return True


class KronotermHeatPumpSwitch(CoordinatorEntity, SwitchEntity):
    """
    Switch to turn the Kronoterm heat pump ON/OFF.

    The ON/OFF state is read directly from Modbus register 2000:
      - 1 => ON
      - 0 => OFF
    We call async_set_heatpump_state(True/False) to change it.
    """

    def __init__(
        self,
        entry: ConfigEntry,
        parent_coordinator,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Kronoterm heat pump switch."""
        super().__init__(coordinator)

        self._parent_coordinator = parent_coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_heatpump_switch"
        self._attr_name = "Heat Pump ON/OFF"
        self._attr_device_info = parent_coordinator.shared_device_info

    @property
    def is_on(self) -> bool:
        """
        Return True if Modbus register 2000 has value=1, else False.
        Falls back to OFF if we can't find the register or data is unavailable.
        """
        data = self.coordinator.data
        if not data:
            return False  # No data yet, assume OFF

        modbus_list = data.get("ModbusReg", [])
        # Find the register 2000
        reg_2000 = next((r for r in modbus_list if r.get("address") == 2000), None)
        if not reg_2000:
            return False

        raw_value = reg_2000.get("value", 0)
        return bool(raw_value)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the heat pump by calling the parent's method."""
        success = await self._parent_coordinator.async_set_heatpump_state(True)
        if success:
            # Immediately request refresh so is_on updates quickly
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on the heat pump via Kronoterm API")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the heat pump by calling the parent's method."""
        success = await self._parent_coordinator.async_set_heatpump_state(False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off the heat pump via Kronoterm API")

class DHWCirculationSwitch(CoordinatorEntity, SwitchEntity):
    """
    Switch to turn the DHW Circulation ON/OFF.

    The ON/OFF state is read directly from Modbus register 2028:
      - 1 => ON
      - 0 => OFF
    We call async_set_heatpump_state(True/False) to change it.
    """

    def __init__(
        self,
        entry: ConfigEntry,
        parent_coordinator,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the DHW Circulation switch."""
        super().__init__(coordinator)

        self._parent_coordinator = parent_coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_dhw_circulation_switch"
        self._attr_name = "DHW Circulation ON/OFF"
        self._attr_device_info = parent_coordinator.shared_device_info

    @property
    def is_on(self) -> bool:
        """
        Return True if Modbus register 2028 has value=1, else False.
        Falls back to OFF if we can't find the register or data is unavailable.
        """
        data = self.coordinator.data
        if not data:
            return False  # No data yet, assume OFF

        modbus_list = data.get("ModbusReg", [])
        # Find the register 2028
        reg_2028 = next((r for r in modbus_list if r.get("address") == 2028), None)
        if not reg_2028:
            return False

        raw_value = reg_2028.get("value", 0)
        return bool(raw_value)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the DHW circulation by calling the parent's method."""
        success = await self._parent_coordinator.async_set_dhw_circulation(True)
        if success:
            # Immediately request refresh so is_on updates quickly
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on the DHW circulation via Kronoterm API")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the DHW circulation by calling the parent's method."""
        success = await self._parent_coordinator.async_set_dhw_circulation(False)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off the DHW circulation via Kronoterm API")

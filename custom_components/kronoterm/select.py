import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kronoterm select entities for Loop 1, Loop 2, and Sanitary Water operation."""
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator

    # Get the ModbusReg list to check if each register exists
    modbus_data = main_coordinator.data or {}
    modbus_list = modbus_data.get("ModbusReg", [])

    entities = []

    # Loop 1: Check for register 2042
    if any(r.get("address") == 2042 for r in modbus_list):
        entities.append(
            KronotermModeSelect(
                entry=entry,
                name="Loop 1 Operation",
                address=2042,
                page=5,
                parent_coordinator=parent_coordinator,
                coordinator=main_coordinator,
            )
        )
    else:
        _LOGGER.info("Loop 1 register (2042) not found, skipping Loop 1 select entity.")

    # Loop 2: Check for register 2052
    if any(r.get("address") == 2052 for r in modbus_list):
        entities.append(
            KronotermModeSelect(
                entry=entry,
                name="Loop 2 Operation",
                address=2052,
                page=6,
                parent_coordinator=parent_coordinator,
                coordinator=main_coordinator,
            )
        )
    else:
        _LOGGER.info("Loop 2 register (2052) not found, skipping Loop 2 select entity.")

    # Sanitary Water: Check for register 2026
    if any(r.get("address") == 2026 for r in modbus_list):
        entities.append(
            KronotermModeSelect(
                entry=entry,
                name="Sanitary Water Operation",
                address=2026,
                page=9,
                parent_coordinator=parent_coordinator,
                coordinator=main_coordinator,
            )
        )
    else:
        _LOGGER.info("Sanitary register (2026) not found, skipping Sanitary select entity.")

    async_add_entities(entities, update_before_add=True)


class KronotermModeSelect(CoordinatorEntity, SelectEntity):
    """
    Select entity for Kronoterm that presents three options: OFF, ON, AUTO.
    It reads the current state from the ModbusReg entry with the given address.
    """

    _attr_options = ["OFF", "ON", "AUTO"]

    def __init__(
        self,
        entry: ConfigEntry,
        name: str,
        address: int,
        page: int,
        parent_coordinator,
        coordinator,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._parent_coordinator = parent_coordinator
        self._address = address
        self._page = page

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{address}_mode"
        self._attr_device_info = parent_coordinator.shared_device_info

    @property
    def current_option(self) -> str | None:
        """Return 'OFF', 'ON', or 'AUTO' based on the Modbus register value."""
        data = self.coordinator.data or {}
        modbus_list = data.get("ModbusReg", [])
        reg = next((r for r in modbus_list if r.get("address") == self._address), None)
        if reg is None:
            return None
        raw_val = reg.get("value")
        if raw_val is None:
            return None
        try:
            # Convert to a float then int (in case it's a string like "0" or "0.0")
            val = int(float(raw_val))
        except (ValueError, TypeError):
            return None
        if val == 0:
            return "OFF"
        elif val == 1:
            return "ON"
        elif val == 2:
            return "AUTO"
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the new mode by mapping OFF->0, ON->1, AUTO->2."""
        if option == "OFF":
            new_mode = 0
        elif option == "ON":
            new_mode = 1
        elif option == "AUTO":
            new_mode = 2
        else:
            _LOGGER.warning("Unknown option: %s", option)
            return

        success = await self._parent_coordinator.async_set_loop_mode_by_page(self._page, new_mode)
        if success:
            await self.coordinator.async_request_refresh()

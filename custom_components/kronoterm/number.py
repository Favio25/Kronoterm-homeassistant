"""number.py - Defines Number entities for ECO/COMFORT offsets on three loops."""

import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Loop 1 addresses and page
LOOP1_PAGE         = 5
LOOP1_ECO_ADDR     = 2047
LOOP1_COMFORT_ADDR = 2048

# Loop 2 addresses and page
LOOP2_PAGE         = 6
LOOP2_ECO_ADDR     = 2057
LOOP2_COMFORT_ADDR = 2058

# Sanitary (DHW) addresses and page
SANITARY_PAGE      = 9
SANITARY_ECO_ADDR  = 2030
SANITARY_COMFORT_ADDR = 2031

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Number entities for ECO and COMFORT offsets of Loop1, Loop2, Sanitary."""
    parent_coordinator = hass.data[DOMAIN]["coordinator"]
    main_coordinator = parent_coordinator.main_coordinator

    # We'll define six entities in total
    entities = []

    # Loop 1 ECO => -10..0
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Loop 1 ECO Offset",
            page=LOOP1_PAGE,
            address=LOOP1_ECO_ADDR,
            param_name="circle_eco_offset",
            min_value=-10.0,
            max_value=0.0,
        )
    )
    # Loop 1 COMFORT => 0..10
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Loop 1 COMFORT Offset",
            page=LOOP1_PAGE,
            address=LOOP1_COMFORT_ADDR,
            param_name="circle_comfort_offset",
            min_value=0.0,
            max_value=10.0,
        )
    )

    # Loop 2 ECO => -10..0
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Loop 2 ECO Offset",
            page=LOOP2_PAGE,
            address=LOOP2_ECO_ADDR,
            param_name="circle_eco_offset",
            min_value=-10.0,
            max_value=0.0,
        )
    )
    # Loop 2 COMFORT => 0..10
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Loop 2 COMFORT Offset",
            page=LOOP2_PAGE,
            address=LOOP2_COMFORT_ADDR,
            param_name="circle_comfort_offset",
            min_value=0.0,
            max_value=10.0,
        )
    )

    # Sanitary ECO => -10..0
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Sanitary ECO Offset",
            page=SANITARY_PAGE,
            address=SANITARY_ECO_ADDR,
            param_name="circle_eco_offset",
            min_value=-10.0,
            max_value=0.0,
        )
    )
    # Sanitary COMFORT => 0..10
    entities.append(
        KronotermOffsetNumber(
            entry=entry,
            parent_coordinator=parent_coordinator,
            coordinator=main_coordinator,
            name="Sanitary COMFORT Offset",
            page=SANITARY_PAGE,
            address=SANITARY_COMFORT_ADDR,
            param_name="circle_comfort_offset",
            min_value=0.0,
            max_value=10.0,
        )
    )

    async_add_entities(entities, update_before_add=True)


class KronotermOffsetNumber(CoordinatorEntity, NumberEntity):
    """
    A Number entity that represents an offset (ECO or COMFORT) for a loop or DHW.

    - Reads the current offset from 'ModbusReg' at the specified address.
    - Writes the offset using async_set_offset(page, param_name, new_value).
    """

    def __init__(
        self,
        entry: ConfigEntry,
        parent_coordinator,
        coordinator: DataUpdateCoordinator,
        name: str,
        page: int,
        address: int,
        param_name: str,
        min_value: float,
        max_value: float,
    ):
        super().__init__(coordinator)
        self._entry = entry
        self._parent_coordinator = parent_coordinator
        self._page = page
        self._address = address
        self._param_name = param_name

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{DOMAIN}_{page}_{address}"
        self._attr_device_info = parent_coordinator.shared_device_info

        # Set numeric bounds (e.g. ECO => -10..0, COMFORT => 0..10)
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 0.1

    @property
    def native_unit_of_measurement(self) -> str:
        """Offsets are typically measured in °C."""
        return "°C"

    @property
    def native_value(self) -> float | None:
        """
        Return the current offset from the coordinator data, reading address=<self._address>.
        We assume the offset is in 'ModbusReg' => "value".
        """
        data = self.coordinator.data or {}
        modbus_list = data.get("ModbusReg", [])
        reg = next((x for x in modbus_list if x["address"] == self._address), None)
        if not reg:
            return None

        raw_val = reg.get("value")
        if raw_val is None:
            return None

        # If it's something like "3.0 °C", strip out the "°C" text
        if isinstance(raw_val, str):
            raw_val = raw_val.replace("°C", "").strip()

        try:
            return float(raw_val)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """
        Called by HA when the user sets a new offset. We'll call async_set_offset on the coordinator.
        """
        # Round to one decimal if desired
        offset_val = round(value, 1)
        success = await self._parent_coordinator.async_set_offset(
            page=self._page,
            param_name=self._param_name,
            new_value=offset_val,
        )
        if not success:
            _LOGGER.error("Failed to update offset for %s to %s", self._attr_name, offset_val)
        else:
            # The coordinator refresh should have been called, so the UI updates automatically
            _LOGGER.debug("Successfully set %s => %.1f", self._attr_name, offset_val)

import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    BASE_URL,
    API_QUERIES,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE,
)

_LOGGER = logging.getLogger(__name__)

class KronotermCoordinator(DataUpdateCoordinator):
    """Single coordinator that fetches data (main, shortcuts, loop1, loop2, dhw, consumption) for Kronoterm."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config_entry):
        """Initialize the coordinator with the Home Assistant instance and session."""
        self.hass = hass
        self.session = session
        self.config_entry = config_entry

        # Extract credentials
        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))
        if not self.username or not self.password:
            _LOGGER.error("No username/password found in config entry! Authentication will fail.")
        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Use only the persisted runtime value from options, falling back to DEFAULT_SCAN_INTERVAL.
        scan_interval = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        scan_interval = max(scan_interval, 1)  # Ensure a minimum of 1 minute.
        _LOGGER.info("Kronoterm coordinator update interval set to %d minutes", scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name="kronoterm_unified_coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=scan_interval),
        )



        self.shared_device_info: Dict[str, Any] = {}
        self.reservoir_installed: bool = False

    async def async_initialize(self) -> None:
        """
        Initialize the coordinator with:
          1) First data refresh
          2) One-time info fetch (if desired)
          3) System config parsing
        """
        # 1) Initial data refresh
        await self.async_config_entry_first_refresh()

        # 2) Optionally fetch 'info' once at startup
        await self._async_fetch_info_once()

        # 3) Parse system config
        await self._parse_system_config()

        _LOGGER.info("Kronoterm coordinator initialized successfully")

    async def _parse_system_config(self) -> None:
        """Parse reservoir or other config flags from 'main' data."""
        main_data = (self.data or {}).get("main") or {}
        system_config = main_data.get("SystemConfiguration", {})
        self.reservoir_installed = bool(system_config.get("reservoir_installed", 0))
        _LOGGER.debug("Reservoir installed: %s", self.reservoir_installed)

    async def _async_fetch_info_once(self) -> None:
        """Fetch 'info' data once and store device information."""
        try:
            info_data = await self._fetch_info()
            if info_data is None:
                _LOGGER.warning("No 'info' data returned.")
                return
            if not self.data:
                self.data = {}
            self.data["info"] = info_data
            _LOGGER.debug("Info data fetched: %s", info_data)

            self._parse_device_info(info_data)
        except Exception as e:
            _LOGGER.warning("Failed to fetch 'info' data once: %s", e)

    def _parse_device_info(self, info_data: Dict[str, Any]) -> None:
        """Extract device info from an 'info' response."""
        info_data_section = info_data.get("InfoData", {})
        device_id = info_data_section.get("device_id", "kronoterm")
        pump_model = info_data_section.get("pumpModel", "Unknown Model")
        firmware_version = info_data_section.get("firmware", "Unknown Firmware")

        self.shared_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": "Kronoterm",
            "manufacturer": "Kronoterm",
            "model": pump_model,
            "sw_version": firmware_version,
        }
        _LOGGER.info("Device info parsed - ID: %s, model: %s", device_id, pump_model)

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            data = {}

            # 1) fetch main & shortcuts in parallel
            results = await asyncio.gather(
                self._fetch_main(),
                self._fetch_shortcuts(),
                return_exceptions=True
            )
            main_result, shortcuts_result = results
            if isinstance(main_result, Exception):
                _LOGGER.error("Error fetching main data: %s", main_result)
                main_result = None
            if isinstance(shortcuts_result, Exception):
                _LOGGER.error("Error fetching shortcuts data: %s", shortcuts_result)
                shortcuts_result = None
            data["main"] = main_result
            data["shortcuts"] = shortcuts_result
            _LOGGER.debug("Shortcuts data fetched: %s", shortcuts_result)

            # 2) fetch loop1, loop2, dhw, reservoir in parallel
            try:
                loop1_data, loop2_data, dhw_data, reservoir_data = await asyncio.gather(
                    self._fetch_loop1(),
                    self._fetch_loop2(),
                    self._fetch_dhw(),
                    self._fetch_reservoir(),
                )
                data["loop1"] = loop1_data
                data["loop2"] = loop2_data
                data["dhw"] = dhw_data
                data["reservoir"] = reservoir_data
                #_LOGGER.debug("Loop 1 data fetched: %s", loop1_data)
                #_LOGGER.debug("Loop 2 data fetched: %s", loop2_data)
                #_LOGGER.debug("DHW data fetched: %s", dhw_data)
                #_LOGGER.debug("Reservoir data fetched: %s", reservoir_data)
            except Exception as ex:
                _LOGGER.error("Error fetching loops/dhw/reservoir: %s", ex)
                data["loop1"] = None
                data["loop2"] = None
                data["dhw"] = None
                data["reservoir"] = None

            # 3) fetch consumption last
            try:
                consumption_result = await self._fetch_consumption()
            except Exception as c_exc:
                _LOGGER.error("Error fetching consumption data: %s", c_exc)
                consumption_result = None
            data["consumption"] = consumption_result

            # keep "info" if it was previously loaded
            if self.data and "info" in self.data:
                data["info"] = self.data["info"]

            return data

        except Exception as err:
            raise UpdateFailed(f"Unified update failed: {err}") from err

    # ------------------------------------------------------------------
    #  "Fetch" methods (GET or POST)
    # ------------------------------------------------------------------
    async def _fetch_main(self) -> Optional[Dict[str, Any]]:
        query_params = API_QUERIES["main"]  # e.g. {"TopPage":"5","Subpage":"3"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_shortcuts(self) -> Optional[Dict[str, Any]]:
        query_params = API_QUERIES["shortcuts"]  # e.g. {"TopPage":"1","Subpage":"3"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_info(self) -> Optional[Dict[str, Any]]:
        query_params = API_QUERIES["info"]
        return await self._request_with_retries("GET", query_params)

    async def _fetch_loop1(self):
        query_params = {"TopPage": "1", "Subpage": "5"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_loop2(self):
        query_params = {"TopPage": "1", "Subpage": "6"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_dhw(self):
        query_params = {"TopPage": "1", "Subpage": "9"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_reservoir(self) -> Optional[Dict[str, Any]]:
        query_params = {"TopPage": "1", "Subpage": "4"}
        return await self._request_with_retries("GET", query_params)

    async def _fetch_consumption(self) -> Optional[Dict[str, Any]]:
        query_params = {"TopPage": "4", "Subpage": "4", "Action": "4"}
        
        now = datetime.now()
        year = now.year
        d1 = now.timetuple().tm_yday

        # Optionally read consumption_year/d1 from config
        if (custom_year := self.config_entry.options.get("consumption_year")):
            try:
                year = int(custom_year)
            except ValueError:
                _LOGGER.warning("Invalid consumption_year in options, ignoring.")
        if (custom_d1 := self.config_entry.options.get("consumption_d1")):
            try:
                d1 = int(custom_d1)
            except ValueError:
                _LOGGER.warning("Invalid consumption_d1 in options, ignoring.")

        form_data = [
            ("year", str(year)),
            ("d1", str(d1)),
            ("d2", "0"),
            ("type", "day"),
            # aValues:
            ("aValues[]", "17"),
            # dValues:
            ("dValues[]", "90"),
            ("dValues[]", "0"),
            ("dValues[]", "91"),
            ("dValues[]", "92"),
            ("dValues[]", "1"),
            ("dValues[]", "2"),
            ("dValues[]", "24"),
            ("dValues[]", "71"),
        ]
        return await self._request_with_retries("POST", query_params, form_data=form_data)

    # ------------------------------------------------------------------
    #  HTTP request helpers with retries
    # ------------------------------------------------------------------
    async def _request_with_retries(
        self,
        method: str,
        query_params: Dict[str, str],
        form_data: Optional[List[Tuple[str, str]]] = None,
        attempts: int = MAX_RETRY_ATTEMPTS
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request with automatic retries on failure."""
        for attempt_idx in range(attempts):
            try:
                if method.upper() == "GET":
                    return await self._perform_get(query_params)
                else:
                    return await self._perform_post(query_params, form_data)
            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("%s attempt %d failed: %s", method.upper(), attempt_idx + 1, e)
                if attempt_idx < attempts - 1:
                    # Exponential backoff for retries
                    await asyncio.sleep(RETRY_DELAY_BASE ** attempt_idx)
                else:
                    raise UpdateFailed(f"Max {method} retries reached for {query_params}: {e}")
        return None

    async def _perform_get(
        self, 
        query_params: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        # Always use basic auth
        async with self.session.get(
            BASE_URL, 
            auth=self.auth, 
            params=query_params, 
            timeout=timeout
        ) as response:
            return await self._process_response(response, "GET", query_params)

    async def _perform_post(
        self,
        query_params: Dict[str, str],
        form_data: Optional[List[Tuple[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        # Always use basic auth
        async with self.session.post(
            BASE_URL,
            auth=self.auth,
            params=query_params,
            data=form_data,
            timeout=timeout
        ) as response:
            return await self._process_response(response, "POST", query_params)

    async def _process_response(
        self,
        response: aiohttp.ClientResponse,
        method: str,
        query_params: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        if response.status == 401:
            _LOGGER.error("Unauthorized! Check credentials.")
            return None
        if response.status != 200:
            body = await response.text()
            _LOGGER.error("HTTP %s on %s: %s", response.status, method, body)
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")

        # Parse JSON
        try:
            return await response.json()
        except aiohttp.ContentTypeError as e:
            text = await response.text()
            _LOGGER.error("Invalid JSON response: %s", text[:200])
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e

    # ------------------------------------------------------------------
    #  Set parameters (POST) methods
    # ------------------------------------------------------------------
    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """
        Turn the heat pump ON/OFF via shortcut.
        Expects the 'heatpump_on' field in the Kronoterm API.
        """
        query_params = API_QUERIES["switch"]
        form_data = [
            ("param_name", "heatpump_on"),
            ("param_value", "1" if turn_on else "0"),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await asyncio.sleep(1)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error("Failed to set heatpump_on=%s. Response=%s", turn_on, result)
                return False
        except UpdateFailed as exc:
            _LOGGER.error("Error toggling heatpump_on=%s: %s", turn_on, exc)
            return False

    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        """
        POST request to change temperature for:
          - DHW (page=9)
          - Loop 1 (page=5)
          - Loop 2 (page=6)
          - Reservoir (page=4)
        """
        if page == 9:
            query_params = API_QUERIES["dhw"]
        elif page == 5:
            query_params = API_QUERIES["loop1"]
        elif page == 6:
            query_params = API_QUERIES["loop2"]
        elif page == 4:
            query_params = API_QUERIES["reservoir"]
        else:
            _LOGGER.error("Invalid page number %s for set_temperature", page)
            return False
        
        form_data = [
            ("param_name", "circle_temp"),
            ("param_value", str(round(new_temp, 1))),
            ("page", str(page)),
        ]

        try:
            response_json = await self._request_with_retries("POST", query_params, form_data)
            if response_json and response_json.get("result") == "success":
                _LOGGER.info("Temperature (page=%s) set to %.1f°C successfully.", page, new_temp)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error("Temp update (page=%s) failed. Response=%s", page, response_json)
                return False
        except UpdateFailed as exc:
            _LOGGER.error("Error setting temperature (page=%s): %s", page, exc)
            return False

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """
        POST request to set an ECO/COMFORT offset for loops, DHW, or reservoir.
          - page=4 => reservoir
          - page=5 => loop1
          - page=6 => loop2
          - page=9 => DHW
        param_name might be circle_eco_offset, circle_comfort_offset, etc.
        """
        if page == 5:
            query_params = API_QUERIES["loop1"]
        elif page == 6:
            query_params = API_QUERIES["loop2"]
        elif page == 9:
            query_params = API_QUERIES["dhw"]
        elif page == 4:
            query_params = API_QUERIES["reservoir"]
        else:
            _LOGGER.error("Invalid page=%s for set_offset. Must be 4,5,6,9.", page)
            return False
        
        form_data = [
            ("param_name", param_name),
            ("param_value", str(round(new_value, 1))),
            ("page", str(page)),
        ]

        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                _LOGGER.info("Offset %s (page=%s) set to %.1f°C successfully.", param_name, page, new_value)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(
                    "Failed to set offset param=%s page=%s to %.1f. Response=%s",
                    param_name, page, new_value, result
                )
                return False
        except UpdateFailed as exc:
            _LOGGER.error(
                "Error in set_offset param=%s page=%s to %.1f: %s",
                param_name, page, new_value, exc
            )
            return False

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        """
        POST request to set the loop/DHW/reservoir mode to 'OFF'(0), 'ON'(1), or 'AUTO'(2).
          - page=4 => Reservoir
          - page=5 => Loop 1
          - page=6 => Loop 2
          - page=9 => DHW
        """
        if page == 5:
            query_params = API_QUERIES["loop1"]
        elif page == 6:
            query_params = API_QUERIES["loop2"]
        elif page == 9:
            query_params = API_QUERIES["dhw"]
        elif page == 4:
            query_params = API_QUERIES["reservoir"]
        else:
            _LOGGER.error("Invalid page=%s for set_loop_mode. Must be 4,5,6,9.", page)
            return False
        
        form_data = [
            ("param_name", "circle_status"),
            ("param_value", str(new_mode)),  # "0", "1", or "2"
            ("page", str(page)),
        ]

        try:
            response_json = await self._request_with_retries("POST", query_params, form_data)
            if response_json and response_json.get("result") == "success":
                _LOGGER.info("Mode for page=%s set to %s successfully.", page, new_mode)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(
                    "Failed to set loop mode page=%s mode=%s. Server response=%s",
                    page, new_mode, response_json
                )
                return False
        except UpdateFailed as exc:
            _LOGGER.error("Error setting loop mode page=%s mode=%s: %s", page, new_mode, exc)
            return False

    async def async_set_antilegionella(self, enable: bool) -> bool:
        """Enable/disable antilegionella via shortcut."""
        query_params = API_QUERIES["switch"]
        form_data = [
            ("param_name", "antilegionella"),
            ("param_value", "1" if enable else "0"),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await asyncio.sleep(2)
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed as exc:
            _LOGGER.error("Failed to set antilegionella=%s: %s", enable, exc)
            return False

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        """Enable/disable DHW circulation."""
        query_params = API_QUERIES["switch"]
        form_data = [
            ("param_name", "circulation_on"),
            ("param_value", "1" if enable else "0"),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await asyncio.sleep(2)
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed as exc:
            _LOGGER.error("Failed to set DHW circulation=%s: %s", enable, exc)
            return False

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        """Enable/disable fast water heating (if supported)."""
        query_params = API_QUERIES["switch"]
        form_data = [
            ("param_name", "water_heating_on"),
            ("param_value", "1" if enable else "0"),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await asyncio.sleep(2)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error("Failed to set fast_water_heating=%s. Response=%s", enable, result)
                return False
        except UpdateFailed as exc:
            _LOGGER.error("Error toggling fast_water_heating=%s: %s", enable, exc)
            return False
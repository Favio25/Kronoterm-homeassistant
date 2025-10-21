import logging
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    BASE_URL,
    API_QUERIES_GET,
    API_QUERIES_SET,
    PAGE_TO_SET_QUERY_KEY,
    API_PARAM_KEYS,
    CONSUMPTION_FORM_DATA_STATIC,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE,
    SHORTCUT_DELAY_DEFAULT,
    SHORTCUT_DELAY_STATE,
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
            name="kronoterm_unified_ coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=scan_interval),
        )

        self._use_basic_auth = True  # Start with Basic Auth enabled

        self.shared_device_info: Dict[str, Any] = {}
        # These flags will be set in _async_fetch_info_once
        self.reservoir_installed: bool = False
        self.pool_installed: bool = False
        self.alt_source_installed: bool = False
        self.loop1_installed: bool = False
        self.loop2_installed: bool = False
        self.loop3_installed: bool = False
        self.loop4_installed: bool = False
        self.tap_water_installed: bool = False


    async def async_initialize(self) -> None:
        """
        Initialize the coordinator with:
          1) First data refresh
          2) One-time info fetch (which also parses system config)
        """
        # 1) Initial data refresh
        await self.async_config_entry_first_refresh()

        # 2) Fetch 'info' once at startup and parse system flags
        await self._async_fetch_info_once()

        _LOGGER.info("Kronoterm coordinator initialized successfully")

    async def _async_fetch_info_once(self) -> None:
        """
        Fetch 'info' data once, store it, and parse system config
        (device info, pool status, reservoir status) from it.
        """
        try:
            info_data = await self._fetch_info()
            if info_data is None:
                _LOGGER.warning("No 'info' data returned.")
                raise UpdateFailed("No 'info' data returned from API")
            if not self.data:
                self.data = {}
            self.data["info"] = info_data
            _LOGGER.debug("Info data fetched: %s", info_data)

            # Parse device info (model, firmware, etc.)
            self._parse_device_info(info_data)
            
            # Parse system config flags from 'TemperaturesAndConfig'
            temp_config = info_data.get("TemperaturesAndConfig", {})
            self.pool_installed = bool(temp_config.get("pool_active", 0))
            #self.reservoir_installed = bool(temp_config.get("reservoir_installed", 0))
            self.reservoir_installed = True
            self.alt_source_installed = bool(temp_config.get("alt_source_temp_visible", 0))
            self.loop1_installed = bool(temp_config.get("circle_1_installed", 0))
            self.loop2_installed = bool(temp_config.get("circle_2_installed", 0))
            self.loop3_installed = bool(temp_config.get("circle_3_installed", 0))
            self.loop4_installed = bool(temp_config.get("circle_4_installed", 0))
            self.tap_water_installed = bool(temp_config.get("tap_water_installed", 0))
            _LOGGER.debug(
                "System config parsed: Pool=%s, Reservoir=%s, AltSource=%s, L1=%s, L2=%s, L3=%s, L4=%s",
                self.pool_installed, self.reservoir_installed, self.alt_source_installed,
                self.loop1_installed, self.loop2_installed,
                self.loop3_installed, self.loop4_installed,
                self.tap_water_installed
            )

            # Successfully fetched info, switch to cookie-based auth
            self._use_basic_auth = False
            _LOGGER.info("Successfully fetched info, switching to cookie auth for subsequent requests.")

        except Exception as e:
            _LOGGER.error("Failed to fetch 'info' data during initialization: %s", e)
            # Re-raise the exception to stop the integration setup
            raise

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
            _LOGGER.debug("Main data fetched: %s", main_result)

            # 2) fetch loop1, loop2, loop3, loop4, dhw, reservoir in parallel
            try:
                (
                    loop1_data, 
                    loop2_data, 
                    dhw_data, 
                    reservoir_data, 
                    loop3_data, 
                    loop4_data
                ) = await asyncio.gather(
                    self._fetch_loop1(),
                    self._fetch_loop2(),
                    self._fetch_dhw(),
                    self._fetch_reservoir(),
                    self._fetch_loop3(),
                    self._fetch_loop4(),
                )
                data["loop1"] = loop1_data
                data["loop2"] = loop2_data
                data["dhw"] = dhw_data
                data["reservoir"] = reservoir_data
                data["loop3"] = loop3_data
                data["loop4"] = loop4_data
            except Exception as ex:
                _LOGGER.error("Error fetching loops/dhw/reservoir/pages: %s", ex)
                data["loop1"] = None
                data["loop2"] = None
                data["dhw"] = None
                data["reservoir"] = None
                data["loop3"] = None
                data["loop4"] = None

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
        return await self._request_with_retries("GET", API_QUERIES_GET["main"])

    async def _fetch_shortcuts(self) -> Optional[Dict[str, Any]]:
        return await self._request_with_retries("GET", API_QUERIES_GET["shortcuts"])

    async def _fetch_info(self) -> Optional[Dict[str, Any]]:
        return await self._request_with_retries("GET", API_QUERIES_GET["info"])

    async def _fetch_loop1(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["loop1"])

    async def _fetch_loop2(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["loop2"])

    async def _fetch_dhw(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["dhw"])

    async def _fetch_reservoir(self) -> Optional[Dict[str, Any]]:
        return await self._request_with_retries("GET", API_QUERIES_GET["reservoir"])

    async def _fetch_loop3(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["loop3"])

    async def _fetch_loop4(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["loop4"])

    async def _fetch_consumption(self) -> Optional[Dict[str, Any]]:
        query_params = API_QUERIES_GET["consumption"]
        
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

        # Start with dynamic data
        form_data = [
            ("year", str(year)),
            ("d1", str(d1)),
        ]
        # Add all static data
        form_data.extend(CONSUMPTION_FORM_DATA_STATIC)
        
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
        # Use basic auth ONLY if the flag is set (on first run or after 401)
        async with self.session.get(
            BASE_URL, 
            auth=self.auth if self._use_basic_auth else None, 
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
        # Use basic auth ONLY if the flag is set (on first run or after 401)
        async with self.session.post(
            BASE_URL,
            auth=self.auth if self._use_basic_auth else None,
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
            # Session likely expired. Set flag to re-authenticate with Basic Auth
            # on the next request.
            if not self._use_basic_auth:
                _LOGGER.warning("Session cookie expired. Forcing re-authentication with Basic Auth.")
                self._use_basic_auth = True
            return None
        if response.status != 200:
            body = await response.text()
            _LOGGER.error("HTTP %s on %s: %s", response.status, method, body)
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")

        # --- MODIFIED SECTION ---
        # Read the raw text from the response first
        raw_text = await response.text()

        # Log the full raw text at DEBUG level
        _LOGGER.debug(
            "Full raw response for %s %s: %s",
            method,
            query_params,
            raw_text
        )
        # --- END MODIFIED SECTION ---

        # Parse JSON
        try:
            # Now parse the text we just read
            data = json.loads(raw_text)
            
            # This log will confirm successful parsing
            _LOGGER.debug(
                "Successful JSON parse for %s %s: %s", 
                method, 
                query_params, 
                data
            )
            
            return data
            
        except json.JSONDecodeError as e:
            # Catch parsing errors
            _LOGGER.error("Invalid JSON response (JSONDecodeError): %s", raw_text[:200])
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e

    # ------------------------------------------------------------------
    #  Generic "Set" Helpers
    # ------------------------------------------------------------------

    async def _async_set_page_parameter(
        self, page: int, param_name: str, param_value: str
    ) -> bool:
        """
        Generic helper to set a parameter on a specific page (4, 5, 6, 7, 8, 9).
        POSTs to the corresponding API_QUERY_SET endpoint.
        """
        query_key = PAGE_TO_SET_QUERY_KEY.get(page)
        if not query_key:
            _LOGGER.error(
                "Invalid page=%s for _async_set_page_parameter (param=%s)",
                page,
                param_name,
            )
            return False

        query_params = API_QUERIES_SET[query_key]
        form_data = [
            ("param_name", param_name),
            ("param_value", param_value),
            ("page", str(page)),
        ]

        try:
            response_json = await self._request_with_retries(
                "POST", query_params, form_data
            )
            if response_json and response_json.get("result") == "success":
                _LOGGER.info(
                    "Parameter %s (page=%s) set to %s successfully.",
                    param_name,
                    page,
                    param_value,
                )
                # Request an immediate refresh to reflect the change in HA
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(
                    "Failed to set param=%s page=%s to %s. Response=%s",
                    param_name,
                    page,
                    param_value,
                    response_json,
                )
                return False
        except UpdateFailed as exc:
            _LOGGER.error(
                "Error in _async_set_page_parameter param=%s page=%s: %s",
                param_name,
                page,
                exc,
            )
            return False

    async def _async_set_shortcut(
        self, param_name: str, enable: bool, post_set_delay: int = SHORTCUT_DELAY_DEFAULT
    ) -> bool:
        """
        Generic helper to set a shortcut parameter (page -1) using API_QUERIES_SET["switch"].
        Includes a post-set delay before refreshing.
        """
        query_params = API_QUERIES_SET["switch"]
        param_value = "1" if enable else "0"
        form_data = [
            ("param_name", param_name),
            ("param_value", param_value),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                _LOGGER.info(
                    "Shortcut %s set to %s successfully.", param_name, param_value
                )
                # Some device shortcuts need a moment to process
                if post_set_delay > 0:
                    await asyncio.sleep(post_set_delay)
                await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(
                    "Failed to set shortcut %s=%s. Response=%s",
                    param_name,
                    param_value,
                    result,
                )
                return False
        except UpdateFailed as exc:
            _LOGGER.error(
                "Error toggling shortcut %s=%s: %s", param_name, param_value, exc
            )
            return False

    # ------------------------------------------------------------------
    #  Public "Set" methods (called by platforms)
    # ------------------------------------------------------------------

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """Turn the heat pump ON/OFF via shortcut."""
        return await self._async_set_shortcut(
            API_PARAM_KEYS["HEAT_PUMP"], turn_on, post_set_delay=SHORTCUT_DELAY_STATE
        )

    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        """
        POST request to change temperature for:
          - DHW (page=9)
          - Loop 1 (page=5)
          - Loop 2 (page=6)
          - Loop 3 (page=7)
          - Loop 4 (page=8)
          - Reservoir (page=4)
        """
        return await self._async_set_page_parameter(
            page, API_PARAM_KEYS["TEMP"], str(round(new_temp, 1))
        )

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """
        POST request to set an ECO/COMFORT offset for loops, DHW, or reservoir.
          - page=4 => reservoir
          - page=5 => loop1
          - page=6 => loop2
          - page=7 => loop3
          - page=8 => loop4
          - page=9 => DHW
        """
        # param_name is passed in directly as it can vary (e.g., "circle_eco_offset")
        return await self._async_set_page_parameter(
            page, param_name, str(round(new_value, 1))
        )

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        """
        POST request to set the loop/DHW/reservoir mode to 'OFF'(0), 'ON'(1), or 'AUTO'(2).
          - page=4 => Reservoir
          - page=5 => Loop 1
          - page=6 => Loop 2
          - page=7 => Loop 3
          - page=8 => Loop 4
          - page=9 => DHW
        """
        return await self._async_set_page_parameter(
            page, API_PARAM_KEYS["MODE"], str(new_mode)
        )

    async def async_set_antilegionella(self, enable: bool) -> bool:
        """Enable/disable antilegionella via shortcut."""
        return await self._async_set_shortcut(API_PARAM_KEYS["ANTILEGIONELLA"], enable)

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        """Enable/disable DHW circulation."""
        return await self._async_set_shortcut(API_PARAM_KEYS["CIRCULATION"], enable)

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        """Enable/disable fast water heating (if supported)."""
        return await self._async_set_shortcut(API_PARAM_KEYS["FAST_HEATING"], enable)

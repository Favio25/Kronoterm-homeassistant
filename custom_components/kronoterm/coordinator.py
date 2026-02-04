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
    """Single coordinator that fetches data (main, shortcuts, loops, dhw, consumption) for Kronoterm."""

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
        
        # Store Basic Auth object to send with EVERY request (PhoneGap mode)
        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Scan interval (supports both seconds and legacy minutes)
        # Try new seconds-based setting first, fall back to minutes
        scan_interval_seconds = config_entry.options.get("scan_interval_seconds")
        if scan_interval_seconds is not None:
            scan_interval_seconds = max(scan_interval_seconds, 30)  # Min 30 seconds for cloud API
            _LOGGER.info("Kronoterm coordinator update interval set to %d seconds", scan_interval_seconds)
            interval = timedelta(seconds=scan_interval_seconds)
        else:
            # Backwards compatibility: use minutes
            scan_interval_minutes = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            scan_interval_minutes = max(scan_interval_minutes, 1)
            _LOGGER.info("Kronoterm coordinator update interval set to %d minutes (legacy)", scan_interval_minutes)
            interval = timedelta(minutes=scan_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name="kronoterm_unified_coordinator",
            update_method=self._async_update_data,
            update_interval=interval,
        )

        # Flag to track connectivity state
        self._session_valid = False

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
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Generate headers to mimic the Kronoterm Mobile App (PhoneGap).
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(BASE_URL)
            root_url = f"{parsed.scheme}://{parsed.netloc}/"
        except Exception:
            root_url = BASE_URL

        return {
            "phonegap": "1.5.0",  # REQUIRED: identifies this as the mobile app
            "Accept": "*/*", 
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "X-Requested-With": "XMLHttpRequest", # Critical for JSON response
            "Referer": root_url,
            "Origin": root_url.rstrip("/"),
            "Connection": "keep-alive",
        }

    async def async_initialize(self) -> None:
        """Initialize: Verify auth, then fetch info."""
        # 1. Perform explicit login/check to ensure creds are valid
        await self._perform_login()
        
        # 2. Fetch initial data
        await self.async_config_entry_first_refresh()

        # 3. Parse system info
        await self._async_fetch_info_once()
        _LOGGER.info("Kronoterm coordinator initialized successfully (App Mode)")

    async def _perform_login(self) -> None:
        """
        Perform the initial handshake.
        Crucially, we must call 'Menu=1' to 'prime' the server session 
        with the user's heat pump configuration (hp_id), exactly like the App's LoadSite() function.
        """
        _LOGGER.debug("Performing initial handshake (Menu=1)...")
        try:
            # CHANGE: Use "menu" instead of "info" for the handshake
            query_params = API_QUERIES_GET["menu"]
            
            async with self.session.get(
                BASE_URL, 
                auth=self.auth, 
                params=query_params,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status == 200:
                    # Verify we got a valid session by checking if we got JSON with 'hp_id'
                    try:
                        data = await response.json()
                        if "hp_id" in data:
                            _LOGGER.info("Handshake successful. Session primed for HP ID: %s", data.get("hp_id"))
                            self._session_valid = True
                            return
                        else:
                            _LOGGER.warning("Handshake returned 200 but missing 'hp_id'. Response: %s", data)
                    except Exception:
                        _LOGGER.warning("Handshake returned 200 but invalid JSON.")

                    # Fallback: If Menu=1 failed to parse, we mark as valid but warn
                    self._session_valid = True 
                else:
                    _LOGGER.error("Handshake failed. Status: %s", response.status)
                    self._session_valid = False
        except Exception as e:
            _LOGGER.error("Error during handshake: %s", e)
            self._session_valid = False

    async def _async_fetch_info_once(self) -> None:
        """Fetch 'info' data once and parse system config."""
        try:
            info_data = await self._fetch_info()
            if info_data is None:
                raise UpdateFailed("No 'info' data returned from API")
            if not self.data:
                self.data = {}
            self.data["info"] = info_data
            
            self._parse_device_info(info_data)
            
            temp_config = info_data.get("TemperaturesAndConfig", {})
            self.pool_installed = bool(temp_config.get("pool_active", 0))
            self.reservoir_installed = True
            self.alt_source_installed = bool(temp_config.get("alt_source_temp_visible", 0))
            self.loop1_installed = bool(temp_config.get("circle_1_installed", 0))
            self.loop2_installed = bool(temp_config.get("circle_2_installed", 0))
            self.loop3_installed = bool(temp_config.get("circle_3_installed", 0))
            self.loop4_installed = bool(temp_config.get("circle_4_installed", 0))
            self.tap_water_installed = bool(temp_config.get("tap_water_installed", 0))
            
            _LOGGER.debug("System config parsed successfully.")

        except Exception as e:
            _LOGGER.error("Failed to fetch 'info' data during initialization: %s", e)
            raise

    def _parse_device_info(self, info_data: Dict[str, Any]) -> None:
        """Extract device info from an 'info' response."""
        info_data_section = info_data.get("InfoData", {})
        pump_model = info_data_section.get("pumpModel", "Unknown Model")
        firmware_version = info_data_section.get("firmware", "Unknown Firmware")

        # Use config_entry.entry_id as device identifier to maintain consistency
        # when switching between Cloud and Modbus connection types
        self.shared_device_info = {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Kronoterm Heat Pump",
            "manufacturer": "Kronoterm",
            "model": pump_model,
            "sw_version": firmware_version,
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        # In App Mode, we don't strictly need a session cookie, but if we marked
        # session as invalid, we retry the handshake.
        if not self._session_valid:
            await self._perform_login()

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

            # 2) fetch loops, dhw, reservoir in parallel
            try:
                (
                    loop1_data, 
                    loop2_data, 
                    dhw_data, 
                    reservoir_data, 
                    loop3_data, 
                    loop4_data,
                    main_settings_data,
                    system_data_result
                ) = await asyncio.gather(
                    self._fetch_loop1(),
                    self._fetch_loop2(),
                    self._fetch_dhw(),
                    self._fetch_reservoir(),
                    self._fetch_loop3(),
                    self._fetch_loop4(),
                    self._fetch_main_settings(),
                    self._fetch_system_data(),
                )
                data["loop1"] = loop1_data
                data["loop2"] = loop2_data
                data["dhw"] = dhw_data
                data["reservoir"] = reservoir_data
                data["loop3"] = loop3_data
                data["loop4"] = loop4_data
                data["main_settings"] = main_settings_data
                data["system_data"] = system_data_result
            except Exception as ex:
                _LOGGER.error("Error fetching loops/dhw/reservoir: %s", ex)
                data["loop1"] = None
                data["loop2"] = None
                data["dhw"] = None
                data["reservoir"] = None
                data["loop3"] = None
                data["loop4"] = None
                data["main_settings"] = None
                data["system_data"] = None

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

    async def _fetch_main_settings(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["main_settings"])

    async def _fetch_system_data(self):
        return await self._request_with_retries("GET", API_QUERIES_GET["system_data"])

    async def _fetch_consumption(self) -> Optional[Dict[str, Any]]:
        query_params = API_QUERIES_GET["consumption"]
        now = datetime.now()
        year = now.year
        d1 = now.timetuple().tm_yday
        
        if (custom_year := self.config_entry.options.get("consumption_year")):
            try: year = int(custom_year)
            except ValueError: pass
        if (custom_d1 := self.config_entry.options.get("consumption_d1")):
            try: d1 = int(custom_d1)
            except ValueError: pass

        form_data = [("year", str(year)), ("d1", str(d1))]
        form_data.extend(CONSUMPTION_FORM_DATA_STATIC)
        result = await self._request_with_retries("POST", query_params, form_data=form_data)
        
        # Issue #23 fix: After midnight (00:00-02:00), also fetch yesterday's finalized data
        # Kronoterm recalculates daily energy after midnight, so we need to capture the final value
        if result and 0 <= now.hour < 2 and d1 > 1:  # Only if not Jan 1st
            yesterday_d1 = d1 - 1
            _LOGGER.debug("Fetching yesterday's finalized consumption data (d1=%s)", yesterday_d1)
            yesterday_form_data = [("year", str(year)), ("d1", str(yesterday_d1))]
            yesterday_form_data.extend(CONSUMPTION_FORM_DATA_STATIC)
            
            try:
                yesterday_result = await self._request_with_retries("POST", query_params, form_data=yesterday_form_data)
                if yesterday_result:
                    yesterday_trend = yesterday_result.get("trend_consumption", {})
                    current_trend = result.get("trend_consumption", {})
                    
                    # Update yesterday's values in the current trend array with finalized data
                    # The second-to-last entry in current_trend is yesterday
                    for key in yesterday_trend:
                        if key in current_trend and len(current_trend[key]) >= 2:
                            yesterday_final_value = yesterday_trend[key][-1]  # Last entry from yesterday's fetch
                            yesterday_cached_value = current_trend[key][-2]  # Second-to-last from today's fetch
                            
                            if yesterday_final_value != yesterday_cached_value:
                                _LOGGER.info(
                                    "Updating %s yesterday final: %.3f -> %.3f kWh",
                                    key, yesterday_cached_value, yesterday_final_value
                                )
                                current_trend[key][-2] = yesterday_final_value  # Update with finalized value
                    
                    # Also store separately for reference
                    result["yesterday_final"] = yesterday_trend
                    _LOGGER.info("Captured and applied yesterday's finalized consumption data")
            except Exception as e:
                _LOGGER.warning("Failed to fetch yesterday's consumption data: %s", e)
        
        return result

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
                # Retry logic for 401/403
                if isinstance(e, ClientResponseError) and e.status in (401, 403):
                    _LOGGER.warning("Auth failure. Re-initializing connection.")
                    await self._perform_login()
                    continue

                if attempt_idx < attempts - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE ** attempt_idx)
                else:
                    raise UpdateFailed(f"Max {method} retries reached for {query_params}: {e}")
        return None

    def _get_page_cookies(self, query_params: Dict[str, str]) -> Dict[str, str]:
        """
        Extract expected page cookies from query params.
        Required even in App Mode for server state context.
        """
        cookies = {"lang": "en"}
        if "TopPage" in query_params:
            cookies["CurrentTopPage"] = query_params["TopPage"]
        if "Subpage" in query_params:
            cookies["CurrentSubPage"] = query_params["Subpage"]
        return cookies

    async def _perform_get(self, query_params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        page_cookies = self._get_page_cookies(query_params)

        # App Mode: auth=self.auth must be present!
        async with self.session.get(
            BASE_URL, 
            auth=self.auth,  # Authenticate every request
            params=query_params, 
            headers=self._get_headers(),
            cookies=page_cookies, 
            timeout=timeout
        ) as response:
            return await self._process_response(response, "GET", query_params)

    async def _perform_post(
        self,
        query_params: Dict[str, str],
        form_data: Optional[List[Tuple[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        page_cookies = self._get_page_cookies(query_params)

        # App Mode: auth=self.auth must be present!
        async with self.session.post(
            BASE_URL,
            auth=self.auth, # Authenticate every request
            params=query_params,
            data=form_data,
            headers=self._get_headers(),
            cookies=page_cookies,
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
             raise ClientResponseError(response.request_info, response.history, status=401, message="Unauthorized")

        if response.status != 200:
            body = await response.text()
            _LOGGER.error("HTTP %s on %s: %s", response.status, method, body)
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")

        raw_text = await response.text()
        
        # RESTORED: Log the raw text so you can compare it with the browser response
        _LOGGER.debug("Full raw response for %s %s: %s", method, query_params, raw_text)

        try:
            data = json.loads(raw_text)
            
            # Check for redirect (Session invalid)
            if data.get("result") == "action" and "window.location" in data.get("js", ""):
                 _LOGGER.warning("Server returned redirect despite App Mode.")
                 raise ClientResponseError(response.request_info, response.history, status=401, message="Session Redirect")

            # RESTORED: Log the parsed data
            _LOGGER.debug("Successful JSON parse for %s %s: %s", method, query_params, data)
            return data
            
        except json.JSONDecodeError as e:
            _LOGGER.error("Invalid JSON response: %s", raw_text[:200])
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e

    # ------------------------------------------------------------------
    #  Generic "Set" Helpers
    # ------------------------------------------------------------------

    async def _async_set_page_parameter(
        self, page: int, param_name: str, param_value: str
    ) -> bool:
        """Generic helper to set a parameter on a specific page."""
        query_key = PAGE_TO_SET_QUERY_KEY.get(page)
        if not query_key:
            return False

        query_params = API_QUERIES_SET[query_key]
        form_data = [
            ("param_name", param_name),
            ("param_value", param_value),
            ("page", str(page)),
        ]

        try:
            response_json = await self._request_with_retries("POST", query_params, form_data)
            if response_json and response_json.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False

    async def _async_set_shortcut(
        self, param_name: str, enable: bool, post_set_delay: int = SHORTCUT_DELAY_DEFAULT
    ) -> bool:
        """Generic helper to set a shortcut parameter (page -1)."""
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
                if post_set_delay > 0:
                    await asyncio.sleep(post_set_delay)
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False
    
    async def async_set_main_temp_offset(self, new_value: float) -> bool:
        """Set the main temperature offset (main_temp)."""
        # Uses the "main_settings" query definition we added to const.py
        query_params = API_QUERIES_SET["main_settings"]
        
        # Based on your screenshot, this specific parameter uses page "-1" 
        # inside the form data, even though the URL is TopPage=3/Subpage=11.
        form_data = [
            ("param_name", "main_temp"),
            ("param_value", str(int(new_value))), 
            ("page", "-1"),
        ]
        
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False

    # ------------------------------------------------------------------
    #  Public "Set" methods
    # ------------------------------------------------------------------

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        return await self._async_set_shortcut(
            API_PARAM_KEYS["HEAT_PUMP"], turn_on, post_set_delay=SHORTCUT_DELAY_STATE
        )

    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        return await self._async_set_page_parameter(
            page, API_PARAM_KEYS["TEMP"], str(round(new_temp, 1))
        )

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        return await self._async_set_page_parameter(
            page, param_name, str(round(new_value, 1))
        )

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        return await self._async_set_page_parameter(
            page, API_PARAM_KEYS["MODE"], str(new_mode)
        )

    async def async_set_antilegionella(self, enable: bool) -> bool:
        return await self._async_set_shortcut(API_PARAM_KEYS["ANTILEGIONELLA"], enable)

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        return await self._async_set_shortcut(API_PARAM_KEYS["CIRCULATION"], enable)

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        return await self._async_set_shortcut(API_PARAM_KEYS["FAST_HEATING"], enable)

    async def _async_set_shortcut_with_confirm(
        self, param_name: str, enable: bool, post_set_delay: int = SHORTCUT_DELAY_DEFAULT
    ) -> bool:
        """
        Generic helper to set a shortcut parameter (page -1) with confirmation support.
        
        Some parameters (like reserve_source) require user confirmation.
        The API returns result="question" with a question_id that must be confirmed.
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
            
            if not result:
                return False
            
            # Check if confirmation is required
            if result.get("result") == "question":
                question_id = result.get("question_id")
                _LOGGER.info(
                    "Parameter %s requires confirmation. Question: %s",
                    param_name,
                    result.get("question", "N/A")
                )
                
                if question_id:
                    # Send confirmation
                    confirm_data = [
                        ("question_id", str(question_id)),
                        ("answer", "yes"),  # or "1" - may need adjustment
                    ]
                    confirm_result = await self._request_with_retries("POST", query_params, confirm_data)
                    
                    if confirm_result and confirm_result.get("result") == "success":
                        if post_set_delay > 0:
                            await asyncio.sleep(post_set_delay)
                        await self.async_request_refresh()
                        return True
                    else:
                        _LOGGER.error("Confirmation failed: %s", confirm_result)
                        return False
                else:
                    _LOGGER.error("Question received but no question_id provided")
                    return False
            
            # Standard success path (no confirmation needed)
            elif result.get("result") == "success":
                if post_set_delay > 0:
                    await asyncio.sleep(post_set_delay)
                await self.async_request_refresh()
                return True
            
            # Unknown result
            else:
                _LOGGER.warning("Unexpected result: %s", result.get("result"))
                return False
                
        except UpdateFailed as e:
            _LOGGER.error("Failed to set %s: %s", param_name, e)
            return False

    async def async_set_reserve_source(self, enable: bool) -> bool:
        """
        Set reserve source (backup electric heater, may require confirmation).
        """
        return await self._async_set_shortcut_with_confirm(
            API_PARAM_KEYS["RESERVE_SOURCE"], enable
        )

    async def async_set_additional_source(self, enable: bool) -> bool:
        """
        Set additional source (may require confirmation).
        """
        return await self._async_set_shortcut_with_confirm(
            API_PARAM_KEYS["ADDITIONAL_SOURCE"], enable
        )

    async def async_set_main_mode(self, new_mode: int) -> bool:
        """Set the operational mode (ECO/Auto/Comfort)."""
        query_params = API_QUERIES_SET["main_settings"]
        form_data = [
            ("param_name", API_PARAM_KEYS["MAIN_MODE"]),
            ("param_value", str(new_mode)),
            ("page", "-1"),
        ]
        try:
            result = await self._request_with_retries("POST", query_params, form_data)
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False
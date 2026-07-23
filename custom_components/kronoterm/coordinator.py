import logging
import asyncio
import aiohttp
import json
import random
import time
from datetime import date, datetime, time as datetime_time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.components.recorder.statistics import async_import_statistics, statistics_during_period
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder import get_instance
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .cloud_auth import (
    AUTH_MODE_WEB,
    async_authenticate_cloud,
)
from .identifiers import (
    ENERGY_DATA_KEYS,
    combined_energy_unique_id,
    daily_energy_unique_id,
)
from .energy_history import (
    EMPTY_HISTORY_STOP_DAYS,
    MAX_HISTORY_DAYS,
    cumulative_energy_rows,
    energy_handover_adjustment,
    energy_window_has_data,
    energy_window_length,
    merge_energy_window,
    normalize_energy_series,
    trim_history_to_first_energy,
)

from .const import (
    DOMAIN,
    BASE_URL,
    BASE_URL_DHW,
    API_QUERIES_GET,
    API_QUERIES_GET_DHW,
    API_QUERIES_SET,
    API_QUERIES_SET_DHW,
    PAGE_TO_SET_QUERY_KEY,
    API_PARAM_KEYS,
    CONSUMPTION_FORM_BASE,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE,
    SHORTCUT_DELAY_DEFAULT,
    SHORTCUT_DELAY_STATE,
)

_LOGGER = logging.getLogger(__name__)


class KronotermBaseCoordinator(DataUpdateCoordinator):
    """Base class for Kronoterm coordinators."""
    
    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config_entry, base_url, api_queries_get, api_queries_set):
        self.hass = hass
        self.session = session
        self.config_entry = config_entry
        self.base_url = base_url
        self.api_queries_get = api_queries_get
        self.api_queries_set = api_queries_set
        
        # Extract credentials
        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))
        
        if not self.username or not self.password:
            _LOGGER.error("No username/password found in config entry! Authentication will fail.")
        
        # Store Basic Auth object to send with EVERY request
        self.auth = aiohttp.BasicAuth(self.username, self.password)
        # Login mode: legacy basic-auth (default) or web session cookie
        self._use_web_session = False
        self.auth_mode: str | None = None

        # Read-only health details used by diagnostic entities and downloads.
        self.last_successful_update = None
        self.last_update_duration_ms: float | None = None
        self.last_update_error: str | None = None

        # Scan interval
        scan_interval_seconds = config_entry.options.get("scan_interval_seconds")
        if scan_interval_seconds is not None:
            scan_interval_seconds = max(scan_interval_seconds, 30)
            interval = timedelta(seconds=scan_interval_seconds)
        else:
            scan_interval_minutes = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            scan_interval_minutes = max(scan_interval_minutes, 1)
            interval = timedelta(minutes=scan_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=f"kronoterm_coordinator_{config_entry.entry_id}",
            update_method=self._async_update_data_with_metrics,
            update_interval=interval,
        )

        self._session_valid = False
        self.shared_device_info: Dict[str, Any] = {}
        # Feature flags
        self.reservoir_installed = False
        self.pool_installed = False
        self.alt_source_installed = False
        self.loop1_installed = False
        self.loop2_installed = False
        self.loop3_installed = False
        self.loop4_installed = False
        self.tap_water_installed = False
        self.system_type = config_entry.data.get("system_type", "cloud")

    async def _async_update_data_with_metrics(self) -> Dict[str, Any]:
        """Run an update while recording non-sensitive health metrics."""
        started = time.monotonic()
        try:
            data = await self._async_update_data()
        except Exception as err:
            self.last_update_duration_ms = round(
                (time.monotonic() - started) * 1000, 1
            )
            self.last_update_error = type(err).__name__
            raise

        self.last_update_duration_ms = round(
            (time.monotonic() - started) * 1000, 1
        )
        self.last_successful_update = dt_util.now()
        self.last_update_error = None
        return data

    async def async_initialize(self) -> None:
        """Initialize: Verify auth, then fetch info."""
        await self._perform_login()
        await self.async_config_entry_first_refresh()
        await self._async_fetch_info_once()
        _LOGGER.info("Kronoterm coordinator initialized successfully")

    async def _perform_login(self) -> None:
        """Authenticate using the same confirmed flow as config validation."""
        self._session_valid = False
        mode = await async_authenticate_cloud(
            self.session,
            base_url=self.base_url,
            menu_params=self.api_queries_get["menu"],
            basic_headers=self._get_headers(use_web_session=False),
            web_headers=self._get_headers(use_web_session=True),
            username=self.username,
            password=self.password,
            attempts=3,
        )
        if mode is None:
            raise ConfigEntryAuthFailed("Unable to authenticate with Kronoterm Cloud")

        self._use_web_session = mode == AUTH_MODE_WEB
        self.auth_mode = mode
        self._session_valid = True
        _LOGGER.info("Kronoterm Cloud authentication succeeded using %s mode", mode)

    def _get_headers(self, use_web_session: bool | None = None) -> Dict[str, str]:
        """Generate headers. Overridden by subclasses."""
        raise NotImplementedError

    async def _async_fetch_info_once(self) -> None:
        """Fetch system info. Overridden by subclasses."""
        pass

    async def _request_with_retries(self, method: str, query_params: Dict[str, str], form_data=None, attempts=MAX_RETRY_ATTEMPTS) -> Optional[Dict[str, Any]]:
        """HTTP request with retries."""
        for attempt_idx in range(attempts):
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                page_cookies = self._get_page_cookies(query_params)
                headers = self._get_headers()

                if method.upper() == "GET":
                    async with self.session.get(
                        self.base_url, auth=self.auth if not self._use_web_session else None, params=query_params,
                        headers=headers, cookies=page_cookies, timeout=timeout
                    ) as response:
                        return await self._process_response(response, "GET", query_params)
                else:
                    async with self.session.post(
                        self.base_url, auth=self.auth if not self._use_web_session else None, params=query_params, data=form_data,
                        headers=headers, cookies=page_cookies, timeout=timeout
                    ) as response:
                        return await self._process_response(response, "POST", query_params)
                        
            except (
                ClientResponseError,
                ClientError,
                asyncio.TimeoutError,
                UpdateFailed,
            ) as err:
                _LOGGER.warning(
                    "%s attempt %d/%d failed: %s",
                    method.upper(),
                    attempt_idx + 1,
                    attempts,
                    type(err).__name__,
                )
                if isinstance(err, ClientResponseError) and err.status in (401, 403):
                    _LOGGER.warning("Auth failure. Re-initializing connection.")
                    await self._perform_login()
                    continue
                if attempt_idx < attempts - 1:
                    delay = min(RETRY_DELAY_BASE * (2**attempt_idx), 10)
                    await asyncio.sleep(delay + random.uniform(0, 0.25))
                else:
                    raise UpdateFailed(
                        f"Max {method.upper()} retries reached for Cloud page"
                    ) from err
        return None

    def _get_page_cookies(self, query_params: Dict[str, str]) -> Dict[str, str]:
        cookies = {"lang": "en"}
        if "TopPage" in query_params:
            cookies["CurrentTopPage"] = query_params["TopPage"]
        if "Subpage" in query_params:
            cookies["CurrentSubPage"] = query_params["Subpage"]
        return cookies

    async def _process_response(self, response, method, query_params) -> Optional[Dict[str, Any]]:
        if response.status in (401, 403):
             raise ClientResponseError(response.request_info, response.history, status=response.status, message="Unauthorized")
        if response.status != 200:
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")
        
        raw_text = await response.text()
        _LOGGER.debug(
            "Received Kronoterm response for %s %s (%d bytes)",
            method,
            query_params,
            len(raw_text),
        )
        
        try:
            data = json.loads(raw_text)
            if data.get("result") == "action" and "window.location" in data.get("js", ""):
                 raise ClientResponseError(response.request_info, response.history, status=401, message="Session Redirect")
            return data
        except json.JSONDecodeError as e:
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e
            
    async def _async_update_data(self) -> Dict[str, Any]:
        """Main update loop. Overridden by subclasses."""
        raise NotImplementedError


class KronotermMainCoordinator(KronotermBaseCoordinator):
    """Coordinator for standard Heat Pumps (Main Cloud)."""

    def __init__(self, hass, session, config_entry):
        super().__init__(hass, session, config_entry, BASE_URL, API_QUERIES_GET, API_QUERIES_SET)
        _LOGGER.info("Initializing Kronoterm Main Coordinator")
        self._last_stats_sync_date = None
        self._energy_statistic_ids = None
        self._stats_metadata_reset = False
        self._energy_reimport_lock = asyncio.Lock()
        self.previous_day_energy: dict[str, float] = {}
        self.previous_day_energy_date = None

    async def _fetch_consumption(self, day_offset: int = 0) -> Optional[Dict[str, Any]]:
        """Fetch daily consumption using year + day-of-year params."""
        target = datetime.now().date() + timedelta(days=day_offset)
        form = CONSUMPTION_FORM_BASE + [
            ("year", str(target.year)),
            ("d1", str(target.timetuple().tm_yday)),
        ]
        _LOGGER.debug(
            "Consumption request params: year=%s d1=%s d2=0 type=day",
            target.year,
            target.timetuple().tm_yday,
        )
        try:
            resp = await self._request_with_retries(
                "POST",
                self.api_queries_get["consumption"],
                form,
            )
        except Exception as err:
            _LOGGER.warning("Consumption request failed with %s", err)
            return None

        if resp and "trend_consumption" in resp:
            return resp
        if resp:
            _LOGGER.warning("Consumption response (no trend): %s", resp.get("desc"))
        return resp

    def _get_headers(self, use_web_session: bool | None = None) -> Dict[str, str]:
        if use_web_session is None:
            use_web_session = self._use_web_session
        if use_web_session:
            return {
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://cloud.kronoterm.com/?login=1",
                "Origin": "https://cloud.kronoterm.com",
                "Connection": "keep-alive",
                "User-Agent": "Mozilla/5.0",
            }
        return {
            "phonegap": "1.5.0",
            "Accept": "*/*", 
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url,
            "Origin": "https://cloud.kronoterm.com",
            "Connection": "keep-alive",
        }

    async def _async_fetch_info_once(self) -> None:
        try:
            info_data = await self._request_with_retries("GET", self.api_queries_get["info"])
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
        except Exception as e:
            _LOGGER.error("Failed to fetch 'info' data: %s", e)
            raise

    def _parse_device_info(self, info_data: Dict[str, Any]) -> None:
        info_data_section = info_data.get("InfoData", {})
        self.shared_device_info = {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Kronoterm Heat Pump",
            "manufacturer": "Kronoterm",
            "model": info_data_section.get("pumpModel", "Unknown Model"),
            "sw_version": info_data_section.get("firmware", "Unknown Firmware"),
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self._session_valid:
            await self._perform_login()

        try:
            data = {}
            # 1. Main & Shortcuts
            results = await asyncio.gather(
                self._request_with_retries("GET", self.api_queries_get["main"]),
                self._request_with_retries("GET", self.api_queries_get["shortcuts"]),
                return_exceptions=True
            )
            data["main"] = results[0] if not isinstance(results[0], Exception) else None
            data["shortcuts"] = results[1] if not isinstance(results[1], Exception) else None

            # 2. Loops/DHW/Reservoir. These pages are optional depending on
            # the installation, so one failure must not discard every result.
            page_keys = (
                "loop1",
                "loop2",
                "dhw",
                "reservoir",
                "loop3",
                "loop4",
                "main_settings",
                "system_data",
            )
            loop_results = await asyncio.gather(
                *(
                    self._request_with_retries("GET", self.api_queries_get[key])
                    for key in page_keys
                ),
                return_exceptions=True,
            )
            for key, result in zip(page_keys, loop_results):
                if isinstance(result, Exception):
                    _LOGGER.warning("Unable to fetch optional Cloud page %s: %s", key, result)
                    data[key] = None
                else:
                    data[key] = result

            try:
                data["consumption"] = await self._fetch_consumption()
                try:
                    consumption = data.get("consumption") or {}
                    if isinstance(consumption, dict):
                        trend = consumption.get("trend_consumption", {})
                        _LOGGER.debug(
                            "Consumption fetched: keys=%s trend_keys=%s desc=%s",
                            list(consumption.keys()),
                            list(trend.keys()) if isinstance(trend, dict) else None,
                            consumption.get("desc"),
                        )
                        if "trend_consumption" not in consumption:
                            _LOGGER.debug(
                                "Consumption response has no trend; keys=%s desc=%s",
                                list(consumption.keys()),
                                consumption.get("desc"),
                            )
                    else:
                        _LOGGER.debug(
                            "Unexpected consumption payload type=%s",
                            type(consumption).__name__,
                        )
                except Exception as log_err:
                    _LOGGER.debug("Failed to log consumption data: %s", log_err)
            except Exception as err:
                _LOGGER.warning("Unable to fetch Cloud consumption data: %s", err)
                data["consumption"] = None
            
            if self.data and "info" in self.data:
                data["info"] = self.data["info"]
                
            # Sync previous day's finalized energy statistics once per day
            await self._sync_previous_day_statistics()
            return data
        except Exception as err:
            raise UpdateFailed(f"Main update failed: {err}") from err

    # Setter methods for Main Cloud (kept from original class)
    async def _async_set_page_parameter(self, page: int, param_name: str, param_value: str) -> bool:
        query_key = PAGE_TO_SET_QUERY_KEY.get(page)
        if not query_key: return False
        form_data = [("param_name", param_name), ("param_value", param_value), ("page", str(page))]
        return await self._send_set_request(query_key, form_data)

    async def _async_set_shortcut(self, param_name: str, enable: bool) -> bool:
        form_data = [("param_name", param_name), ("param_value", "1" if enable else "0"), ("page", "-1")]
        return await self._send_set_request("switch", form_data)

    async def _send_set_request(self, query_key, form_data):
        try:
            _LOGGER.debug(
                "Sending Kronoterm SET request: query_key=%s fields=%s",
                query_key,
                sorted(key for key, _value in form_data),
            )
            result = await self._request_with_retries("POST", self.api_queries_set[query_key], form_data)
            _LOGGER.debug(
                "Kronoterm SET response result=%s",
                result.get("result") if isinstance(result, dict) else None,
            )
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            _LOGGER.warning("SET request failed or returned non-success result: %s", result)
            return False
        except UpdateFailed as e:
            _LOGGER.error("SET request raised UpdateFailed: %s", e)
            return False

    # (Add other specific setters here if needed, keeping it minimal for now)
    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        return await self._async_set_page_parameter(page, API_PARAM_KEYS["TEMP"], str(round(new_temp, 1)))

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """Set eco/comfort offsets for cloud loops/DHW."""
        return await self._async_set_page_parameter(page, param_name, str(round(new_value, 1)))

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        return await self._async_set_page_parameter(page, API_PARAM_KEYS["MODE"], str(new_mode))

    async def async_set_main_mode(self, new_mode: int) -> bool:
        """Set operational mode (auto/comfort/eco) via main_settings."""
        _LOGGER.info("Setting operational mode to %d via cloud API", new_mode)
        form_data = [
            ("param_name", API_PARAM_KEYS["MAIN_MODE"]),
            ("param_value", str(new_mode)),
            ("page", "11"),
        ]
        result = await self._send_set_request("main_settings", form_data)
        _LOGGER.info("Operational mode change %s", "succeeded" if result else "failed")
        return result

    async def async_set_main_temp_offset(self, value: float) -> bool:
        """Set system temperature correction via main_settings."""
        _LOGGER.info("Setting main temperature offset to %.1f via cloud API", value)
        form_data = [
            ("param_name", "main_temp"),
            ("param_value", str(int(value))),
            ("page", "-1"),
        ]
        result = await self._send_set_request("main_settings", form_data)
        _LOGGER.info("Main temperature offset change %s", "succeeded" if result else "failed")
        return result

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """Turn heat pump on/off via shortcuts."""
        return await self._async_set_shortcut(API_PARAM_KEYS["HEAT_PUMP"], turn_on)

    async def async_set_fast_water_heating(self, enable: bool) -> bool:
        """Enable/disable fast DHW heating via shortcuts."""
        return await self._async_set_shortcut(API_PARAM_KEYS["FAST_HEATING"], enable)

    async def async_set_dhw_circulation(self, enable: bool) -> bool:
        """Enable/disable DHW circulation via shortcuts (if supported)."""
        return await self._async_set_shortcut(API_PARAM_KEYS["CIRCULATION"], enable)

    async def async_set_antilegionella(self, enable: bool) -> bool:
        """Enable/disable antilegionella via shortcuts."""
        return await self._async_set_shortcut(API_PARAM_KEYS["ANTILEGIONELLA"], enable)

    async def async_set_reserve_source(self, enable: bool) -> bool:
        """Enable/disable reserve source via shortcuts."""
        return await self._async_set_shortcut(API_PARAM_KEYS["RESERVE_SOURCE"], enable)

    async def async_set_additional_source(self, enable: bool) -> bool:
        """Enable/disable additional source via shortcuts."""
        return await self._async_set_shortcut(API_PARAM_KEYS["ADDITIONAL_SOURCE"], enable)

    async def _sync_previous_day_statistics(self) -> None:
        """Re-import finalized daily energy statistics for yesterday after midnight."""
        today = dt_util.now().date()
        if self._last_stats_sync_date == today:
            return

        consumption = await self._fetch_consumption(day_offset=-1)
        if not consumption or "trend_consumption" not in consumption:
            _LOGGER.debug("No consumption data for previous day; skipping stats sync")
            return

        target_date = today - timedelta(days=1)
        trend = consumption.get("trend_consumption", {})
        finalized: dict[str, float] = {}
        for key in ENERGY_DATA_KEYS:
            values = trend.get(key, [])
            if values:
                finalized[key] = float(values[-1])
        if not finalized:
            _LOGGER.debug("Previous-day energy response contained no values")
            return
        finalized["combined"] = sum(finalized.values())
        self.previous_day_energy = finalized
        self.previous_day_energy_date = target_date

        await self._import_energy_statistics_for_date(target_date, consumption)
        self._last_stats_sync_date = today
        _LOGGER.info("Re-imported previous day energy statistics")

    async def _fetch_consumption_for_date(self, target_date: datetime.date) -> Optional[Dict[str, Any]]:
        """Fetch consumption for a specific date."""
        form = CONSUMPTION_FORM_BASE + [
            ("year", str(target_date.year)),
            ("d1", str(target_date.timetuple().tm_yday)),
        ]
        try:
            return await self._request_with_retries(
                "POST",
                self.api_queries_get["consumption"],
                form,
            )
        except Exception as err:
            _LOGGER.debug("Consumption request failed for %s: %s", target_date, err)
            return None

    async def _import_energy_statistics_for_date(self, target_date: datetime.date, consumption: Dict[str, Any]) -> None:
        if isinstance(target_date, (int, float)):
            target_date = dt_util.as_local(dt_util.utc_from_timestamp(target_date)).date()
        elif isinstance(target_date, datetime):
            target_date = target_date.date()

        trend = consumption.get("trend_consumption", {})
        keys = list(ENERGY_DATA_KEYS)
        series_map = {k: [float(v) for v in trend.get(k, [])] for k in keys}
        length = max((len(v) for v in series_map.values()), default=0)
        if length == 0:
            return

        window_start = target_date - timedelta(days=length - 1)
        index = (target_date - window_start).days

        entity_ids = await self._get_energy_statistic_entity_ids()
        if not entity_ids:
            return

        for key, entity_id in entity_ids.items():
            if key != "combined" and key not in series_map:
                continue

            if key == "combined":
                value = 0.0
                for k in keys:
                    values = series_map.get(k, [])
                    if index < len(values):
                        value += values[index]
            else:
                values = series_map.get(key, [])
                if index >= len(values):
                    continue
                value = values[index]

            last_sum = await self._get_last_statistics_sum(entity_id)
            running_sum = last_sum + value

            start_local = datetime.combine(
                target_date,
                datetime.min.time(),
                tzinfo=dt_util.DEFAULT_TIME_ZONE,
            )
            start = dt_util.as_utc(start_local)
            stats = [{
                "start": start,
                "state": running_sum,
                "sum": running_sum,
                "last_reset": None,
            }]

            metadata = {
                "statistic_id": entity_id,
                "source": "recorder",
                "name": entity_id,
                "unit_of_measurement": "kWh",
                "unit_class": "energy",
                "has_sum": True,
                "has_mean": False,
                "mean_type": StatisticMeanType.NONE,
            }

            async_import_statistics(self.hass, metadata, stats)

    async def _get_energy_statistic_entity_ids(self) -> Optional[Dict[str, str]]:
        if self._energy_statistic_ids is not None:
            return self._energy_statistic_ids

        keys = list(ENERGY_DATA_KEYS)
        key_to_unique = {
            key: daily_energy_unique_id(self.config_entry.entry_id, key)
            for key in keys
        }
        combined_unique = combined_energy_unique_id(self.config_entry.entry_id, keys)

        registry = er.async_get(self.hass)
        result = {}
        for key, unique_id in key_to_unique.items():
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id:
                result[key] = entity_id
        combined_id = registry.async_get_entity_id("sensor", DOMAIN, combined_unique)
        if combined_id:
            result["combined"] = combined_id

        self._energy_statistic_ids = result
        return result

    async def _ensure_energy_statistics_metadata(self) -> None:
        if self._stats_metadata_reset:
            return

        entity_ids = await self._get_energy_statistic_entity_ids()
        if not entity_ids:
            return

        recorder = get_instance(self.hass)
        recorder.async_clear_statistics(list(entity_ids.values()))
        self._stats_metadata_reset = True

    async def _get_last_statistics_sum(self, entity_id: str) -> float:
        start_window = dt_util.utcnow() - timedelta(days=14)

        def _fetch():
            return statistics_during_period(
                self.hass,
                start_window,
                None,
                {entity_id},
                "day",
                None,
                {"sum"},
            )

        recorder = get_instance(self.hass)
        stats = await recorder.async_add_executor_job(_fetch)
        rows = stats.get(entity_id, [])
        if not rows:
            return 0.0
        return float(rows[-1].get("sum") or 0.0)

    async def _get_energy_statistics(
        self,
        entity_ids: set[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Return enough hourly statistics to locate the live-data handover."""
        start = dt_util.utcnow() - timedelta(days=MAX_HISTORY_DAYS)

        def _fetch():
            return statistics_during_period(
                self.hass,
                start,
                None,
                entity_ids,
                "hour",
                None,
                {"sum"},
            )

        recorder = get_instance(self.hass)
        return await recorder.async_add_executor_job(_fetch)

    @staticmethod
    def _statistics_start_as_local(value: Any) -> datetime | None:
        """Normalize a statistics start value and convert it to local time."""
        if isinstance(value, (int, float)):
            value = dt_util.utc_from_timestamp(value)
        elif isinstance(value, str):
            value = dt_util.parse_datetime(value)
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_util.UTC)
        return dt_util.as_local(value)

    def _find_energy_handover_date(
        self,
        existing: dict[str, list[dict[str, Any]]],
    ) -> date:
        """Find the first day containing recorder-generated hourly rows."""
        candidates: list[date] = []
        for rows in existing.values():
            for row in rows:
                start = self._statistics_start_as_local(row.get("start"))
                if start is None or start.time() == datetime_time.min:
                    continue
                candidates.append(start.date())
                break

        return min(candidates) if candidates else dt_util.now().date()

    def _energy_handover_adjustments(
        self,
        handover_date: date,
        existing: dict[str, list[dict[str, Any]]],
    ) -> dict[str, tuple[datetime, float]]:
        """Calculate corrections at each entity's first actual live row."""
        adjustments: dict[str, tuple[datetime, float]] = {}
        for entity_id, rows in existing.items():
            historical_sum = 0.0
            first_live_sum: float | None = None
            first_live_start: datetime | None = None
            for row in rows:
                start = self._statistics_start_as_local(row.get("start"))
                if start is None:
                    continue
                row_sum = float(row.get("sum") or 0.0)
                is_midnight = (
                    start.hour == 0
                    and start.minute == 0
                    and start.second == 0
                    and start.microsecond == 0
                )
                if start.date() < handover_date or (
                    start.date() == handover_date and is_midnight
                ):
                    historical_sum = row_sum
                elif start.date() >= handover_date and first_live_sum is None:
                    first_live_sum = row_sum
                    first_live_start = start
                    break

            _LOGGER.debug(
                "Energy boundary for %s: historical=%.6f, first_live=%s",
                entity_id,
                historical_sum,
                (
                    f"{first_live_sum:.6f}"
                    if first_live_sum is not None
                    else "missing"
                ),
            )
            adjustment = energy_handover_adjustment(
                historical_sum,
                first_live_sum,
            )
            if first_live_start is not None:
                adjustments[entity_id] = (
                    dt_util.as_utc(first_live_start),
                    adjustment,
                )
        return adjustments

    async def reimport_all_energy_statistics(self) -> None:
        """Rebuild available energy history and join it to live statistics."""
        async with self._energy_reimport_lock:
            await self._reimport_all_energy_statistics()

    async def _reimport_all_energy_statistics(self) -> None:
        """Perform one bounded, monotonic, idempotent energy-history import."""
        entity_ids = await self._get_energy_statistic_entity_ids()
        if not entity_ids:
            _LOGGER.warning("No energy statistic entities found for reimport")
            return

        statistic_ids = set(entity_ids.values())
        existing = await self._get_energy_statistics(statistic_ids)
        handover_date = self._find_energy_handover_date(existing)
        current = min(
            dt_util.now().date() - timedelta(days=1),
            handover_date - timedelta(days=1),
        )
        remaining_days = MAX_HISTORY_DAYS
        empty_history_days = 0
        day_values: dict[date, dict[str, float]] = {}

        while remaining_days > 0:
            consumption = await self._fetch_consumption_for_date(current)
            trend = consumption.get("trend_consumption") if consumption else None
            if trend:
                series_map = normalize_energy_series(trend, ENERGY_DATA_KEYS)
                length = energy_window_length(series_map)
                if length:
                    window = merge_energy_window(
                        day_values,
                        current,
                        series_map,
                        entity_ids,
                        ENERGY_DATA_KEYS,
                    )
                    assert window is not None
                    window_start, window_end = window
                    has_energy = energy_window_has_data(series_map)
                    _LOGGER.info(
                        "Consumption window: %s -> %s (len=%s, energy=%s)",
                        window_start,
                        window_end,
                        length,
                        has_energy,
                    )
                    empty_history_days = (
                        0 if has_energy else empty_history_days + length
                    )
                    current = window_start - timedelta(days=1)
                    remaining_days -= length
                else:
                    empty_history_days += 1
                    current -= timedelta(days=1)
                    remaining_days -= 1
            else:
                empty_history_days += 1
                current -= timedelta(days=1)
                remaining_days -= 1

            if empty_history_days >= EMPTY_HISTORY_STOP_DAYS:
                _LOGGER.info(
                    "Stopping backward scan after %s consecutive empty days",
                    empty_history_days,
                )
                break

        day_values = trim_history_to_first_energy(day_values)
        if not day_values:
            _LOGGER.warning("No non-zero Kronoterm energy history found")
            return

        rows, _totals = cumulative_energy_rows(
            day_values,
            statistic_ids,
            handover_date,
        )
        recorder = get_instance(self.hass)

        for entity_id in statistic_ids:
            imported_rows = []
            for day, running_total in rows[entity_id]:
                start_local = datetime.combine(
                    day,
                    datetime.min.time(),
                    tzinfo=dt_util.DEFAULT_TIME_ZONE,
                )
                imported_rows.append({
                    "start": dt_util.as_utc(start_local),
                    "state": running_total,
                    "sum": running_total,
                    "last_reset": None,
                })

            metadata = {
                "statistic_id": entity_id,
                "source": "recorder",
                "name": entity_id,
                "unit_of_measurement": "kWh",
                "unit_class": "energy",
                "has_sum": True,
                "has_mean": False,
                "mean_type": StatisticMeanType.NONE,
            }
            async_import_statistics(self.hass, metadata, imported_rows)

        # Home Assistant may rewrite later sums while imported rows are merged.
        # Wait for that work, inspect the resulting boundary, and only then join
        # the live series to the final historical total. This is idempotent and
        # also repairs offsets left by older versions of the integration.
        await recorder.async_block_till_done()
        post_import = await self._get_energy_statistics(statistic_ids)
        adjustments = self._energy_handover_adjustments(
            handover_date,
            post_import,
        )
        for entity_id in statistic_ids:
            correction = adjustments.get(entity_id)
            if correction is None:
                _LOGGER.debug(
                    "No live statistics boundary found for %s",
                    entity_id,
                )
                continue
            first_live_start, adjustment = correction
            _LOGGER.debug(
                "Energy handover adjustment for %s at %s: %.6f kWh",
                entity_id,
                first_live_start,
                adjustment,
            )
            if abs(adjustment) > 1e-9:
                recorder.async_adjust_statistics(
                    entity_id,
                    first_live_start,
                    adjustment,
                    "kWh",
                )

        await recorder.async_block_till_done()
        self._last_stats_sync_date = dt_util.now().date()
        _LOGGER.info(
            "Re-imported %s days of energy statistics (%s -> %s); "
            "live handover=%s",
            len(day_values),
            min(day_values),
            max(day_values),
            handover_date,
        )


class KronotermDHWCoordinator(KronotermBaseCoordinator):
    """Coordinator for DHW Heat Pumps (Water Cloud)."""

    def __init__(self, hass, session, config_entry):
        super().__init__(hass, session, config_entry, BASE_URL_DHW, API_QUERIES_GET_DHW, API_QUERIES_SET_DHW)
        _LOGGER.info("Initializing Kronoterm DHW Coordinator")
        self.system_type = "dhw"
        # Ensure we don't accidentally check flags that don't exist
        self.tap_water_installed = True 

    def _get_headers(self, use_web_session: bool | None = None) -> Dict[str, str]:
        if use_web_session is None:
            use_web_session = self._use_web_session
        if use_web_session:
            return {
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://cloud.kronoterm.com/dhws/?login=1",
                "Origin": "https://cloud.kronoterm.com",
                "Connection": "keep-alive",
                "User-Agent": "Mozilla/5.0",
            }
        return {
            "phonegap": "1.0.7",
            "Accept": "*/*", 
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url,
            "Origin": "https://cloud.kronoterm.com",
            "Connection": "keep-alive",
        }

    async def _async_fetch_info_once(self) -> None:
        # DHW doesn't have an "info" page like Main. 
        # We fetch "main" to get basic info if needed.
        # Just set device info manually for now based on what we know.
        self.shared_device_info = {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Kronoterm DHW",
            "manufacturer": "Kronoterm",
            "model": "DHW Heat Pump",
            "sw_version": "Unknown",
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self._session_valid:
            await self._perform_login()

        try:
            data = {}
            # Fetch Main (Basic Data) and Shortcuts
            results = await asyncio.gather(
                self._request_with_retries("GET", self.api_queries_get["main"]),
                self._request_with_retries("GET", self.api_queries_get["shortcuts"]),
                return_exceptions=True
            )
            
            data["main"] = results[0] if not isinstance(results[0], Exception) else None
            data["shortcuts"] = results[1] if not isinstance(results[1], Exception) else None
            
            # Nullify others to be safe
            for key in ["loop1", "loop2", "dhw", "reservoir", "loop3", "loop4", "main_settings", "system_data", "info", "consumption"]:
                data[key] = None
                
            return data
        except Exception as err:
            raise UpdateFailed(f"DHW update failed: {err}") from err

    # Setter methods for DHW
    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        # DHW Temp is usually on page 1 ("main")
        form_data = [
            ("param_name", "boiler_setpoint"),
            ("param_value", str(round(new_temp, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_luxury_shower(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_luxury_shower", enable)

    async def async_set_antilegionella(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_antilegionela", enable)

    async def async_set_reserve_source(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_reserve_source", enable)

    async def async_set_additional_source(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_add_source", enable)

    async def async_set_holiday(self, enable: bool) -> bool:
        # Use current holiday_days if available
        days = 0
        try:
            days = int(
                self.data.get("shortcuts", {})
                .get("ShortcutsData", {})
                .get("holiday_days", 0)
            )
        except Exception:
            days = 0
        return await self._send_shortcut("shrtct_holiday", enable, additional_value=days)

    async def async_set_dhw_eco_offset(self, value: float) -> bool:
        form_data = [
            ("param_name", "boiler_eco_offset"),
            ("param_value", str(round(value, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_dhw_comfort_offset(self, value: float) -> bool:
        form_data = [
            ("param_name", "boiler_comfort_offset"),
            ("param_value", str(round(value, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_dhw_default_mode(self, mode: int) -> bool:
        form_data = [
            ("param_name", "default_mode"),
            ("param_value", str(int(mode))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def _send_shortcut(self, param_name: str, enable: bool, additional_value: Optional[int] = None) -> bool:
        form_data = [
            ("param_name", param_name),
            ("param_value", "1" if enable else "0"),
            ("page", "2"),
        ]
        if additional_value is not None:
            form_data.append(("additional_value", str(additional_value)))
        return await self._send_set_request("shortcuts", form_data)

    async def _send_set_request(self, query_key, form_data):
        try:
            result = await self._request_with_retries("POST", self.api_queries_set[query_key], form_data)
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False

# Compatibility alias for existing code
KronotermCoordinator = KronotermMainCoordinator

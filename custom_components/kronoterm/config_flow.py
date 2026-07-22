import logging
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT

from .const import (
    DOMAIN, 
    CONFIG_ENTRY_VERSION,
    BASE_URL, 
    BASE_URL_DHW,
    API_QUERIES_GET,
    API_QUERIES_GET_DHW,
    DEFAULT_SCAN_INTERVAL, 
)

from .config_flow_modbus import (
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_MODBUS,
    MODBUS_TRANSPORT_TCP,
    MODBUS_TRANSPORT_RTU,
    validate_modbus_connection,
    get_connection_type_schema,
    get_modbus_transport_schema,
    get_modbus_tcp_schema,
    get_modbus_rtu_schema,
)

from .entity_cleanup import (
    disable_mode_specific_entities,
    enable_mode_specific_entities,
)
from .cloud_auth import async_authenticate_cloud
from .identifiers import cloud_config_unique_id, modbus_config_unique_id

_LOGGER = logging.getLogger(__name__)

SENSITIVE_KEYS = [CONF_USERNAME, CONF_PASSWORD]

def sanitize_user_input(user_input: dict) -> dict:
    """
    Sanitizes user input by redacting sensitive information for logging purposes.
    """
    return {
        key: ("[REDACTED]" if key in SENSITIVE_KEYS else value)
        for key, value in user_input.items()
    }

async def validate_credentials(data: dict, preferred_type: str = "auto") -> tuple[str | None, str | None]:
    """
    Validate the credentials by attempting a lightweight API call.
    Returns (error_code, system_type) on failure/success.
    
    preferred_type: "auto" | "cloud" | "dhw"
    """
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    async def _try_endpoint(
        base_url: str,
        menu_params: dict[str, str],
        phonegap_version: str,
    ) -> bool:
        basic_headers = {
            "phonegap": phonegap_version,
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": base_url,
            "Origin": "https://cloud.kronoterm.com",
        }
        web_headers = {
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                "https://cloud.kronoterm.com/dhws/?login=1"
                if "/dhws/" in base_url
                else "https://cloud.kronoterm.com/?login=1"
            ),
            "Origin": "https://cloud.kronoterm.com",
            "User-Agent": "Mozilla/5.0",
        }
        async with aiohttp.ClientSession() as session:
            mode = await async_authenticate_cloud(
                session,
                base_url=base_url,
                menu_params=menu_params,
                basic_headers=basic_headers,
                web_headers=web_headers,
                username=username,
                password=password,
            )
        return mode is not None

    async def _try_main() -> bool:
        return await _try_endpoint(BASE_URL, API_QUERIES_GET["menu"], "1.5.0")

    async def _try_dhw() -> bool:
        return await _try_endpoint(BASE_URL_DHW, API_QUERIES_GET_DHW["menu"], "1.0.7")

    if preferred_type == "cloud":
        ok = await _try_main()
        return (None, "cloud") if ok else ("invalid_auth", None)
    if preferred_type == "dhw":
        ok = await _try_dhw()
        return (None, "dhw") if ok else ("invalid_auth", None)

    if await _try_main():
        return None, "cloud"
    if await _try_dhw():
        return None, "dhw"
    return "invalid_auth", None



class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles the configuration flow for the Kronoterm integration.
    """
    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.connection_type = None
        self.modbus_transport = MODBUS_TRANSPORT_TCP
        self.reconfig_entry = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initialized by the user - choose connection type."""
        _LOGGER.debug("Starting user step in KronotermConfigFlow")
        
        if user_input is not None:
            # Store connection type and move to appropriate step
            self.connection_type = user_input.get("connection_type", CONNECTION_TYPE_CLOUD)
            _LOGGER.debug("Connection type selected: %s", self.connection_type)
            
            if self.connection_type == CONNECTION_TYPE_MODBUS:
                return await self.async_step_modbus_transport()
            else:
                return await self.async_step_cloud()
        
        # Show connection type selection
        return self.async_show_form(
            step_id="user",
            data_schema=get_connection_type_schema(),
        )

    async def async_step_cloud(self, user_input: dict | None = None):
        """Handle cloud API configuration."""
        _LOGGER.debug("Starting cloud API configuration step")
        errors: dict[str, str] = {}

        if user_input is not None:
            sanitized_input = sanitize_user_input(user_input)
            _LOGGER.debug("User input received: %s", sanitized_input)
            
            preferred_type = user_input.get("cloud_type", "auto")
            # Validate credentials
            error_code, system_type = await validate_credentials(user_input, preferred_type)
            
            if not error_code and system_type:
                # Auth success, add connection type and create entry
                user_input["connection_type"] = CONNECTION_TYPE_CLOUD
                user_input["system_type"] = system_type  # Store system type (cloud/dhw)
                await self.async_set_unique_id(
                    cloud_config_unique_id(user_input[CONF_USERNAME], system_type)
                )
                self._abort_if_unique_id_configured()
                
                title = "Kronoterm Heat Pump (Cloud)"
                if system_type == "dhw":
                    title = "Kronoterm DHW (Water Cloud)"
                
                return self.async_create_entry(
                    title=title, 
                    data=user_input
                )
            elif error_code:
                # Auth failed, set error and show form again
                errors["base"] = error_code
            else:
                errors["base"] = "unknown"

        cloud_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required("cloud_type", default="dhw"): vol.In({
                "cloud": "Heating heat pump",
                "dhw": "Sanitary water heat pump",
            }),
        })
        
        return self.async_show_form(
            step_id="cloud", 
            data_schema=cloud_schema,
            errors=errors
        )

    async def async_step_modbus_transport(self, user_input: dict | None = None):
        """Choose Modbus transport (TCP/RTU)."""
        if user_input is not None:
            self.modbus_transport = user_input.get("transport", MODBUS_TRANSPORT_TCP)
            if self.modbus_transport == MODBUS_TRANSPORT_RTU:
                return await self.async_step_modbus_rtu()
            return await self.async_step_modbus_tcp()

        return self.async_show_form(
            step_id="modbus_transport",
            data_schema=get_modbus_transport_schema(),
        )

    async def async_step_modbus_tcp(self, user_input: dict | None = None):
        """Handle Modbus TCP configuration."""
        _LOGGER.debug("Starting Modbus TCP configuration step")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Modbus TCP config received: %s", user_input)
            user_input["transport"] = MODBUS_TRANSPORT_TCP

            # Validate Modbus connection
            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                await self.async_set_unique_id(
                    modbus_config_unique_id(
                        MODBUS_TRANSPORT_TCP,
                        user_input[CONF_HOST],
                        user_input.get(CONF_PORT, 502),
                        user_input.get("unit_id", 20),
                    )
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Kronoterm Heat Pump (Modbus)",
                    data=user_input,
                )
            errors["base"] = error_code

        return self.async_show_form(
            step_id="modbus_tcp",
            data_schema=get_modbus_tcp_schema(),
            errors=errors,
        )

    async def async_step_modbus_rtu(self, user_input: dict | None = None):
        """Handle Modbus RTU configuration."""
        _LOGGER.debug("Starting Modbus RTU configuration step")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Modbus RTU config received: %s", user_input)
            user_input["transport"] = MODBUS_TRANSPORT_RTU

            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                await self.async_set_unique_id(
                    modbus_config_unique_id(
                        MODBUS_TRANSPORT_RTU,
                        user_input["serial_port"],
                        0,
                        user_input.get("unit_id", 20),
                    )
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Kronoterm Heat Pump (Modbus)",
                    data=user_input,
                )
            errors["base"] = error_code

        return self.async_show_form(
            step_id="modbus_rtu",
            data_schema=get_modbus_rtu_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict | None = None):
        """Handle reconfiguration of an existing entry."""
        self.reconfig_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        _LOGGER.info(
            "Starting reconfiguration for entry %s (current type: %s)",
            self.reconfig_entry.entry_id,
            self.reconfig_entry.data.get("connection_type", "cloud")
        )
        return await self.async_step_reconfigure_connection_type(user_input)

    async def async_step_reconfigure_connection_type(self, user_input: dict | None = None):
        """Choose new connection type during reconfiguration."""
        if user_input is not None:
            self.connection_type = user_input.get("connection_type", CONNECTION_TYPE_CLOUD)
            _LOGGER.debug("Reconfigure: New connection type selected: %s", self.connection_type)
            
            if self.connection_type == CONNECTION_TYPE_MODBUS:
                return await self.async_step_reconfigure_modbus_transport()
            else:
                return await self.async_step_reconfigure_cloud()
        
        current_type = self.reconfig_entry.data.get("connection_type", CONNECTION_TYPE_CLOUD)
        current_type_name = "Modbus" if current_type == CONNECTION_TYPE_MODBUS else "Cloud"
        
        return self.async_show_form(
            step_id="reconfigure_connection_type",
            data_schema=get_connection_type_schema(),
            description_placeholders={"current_type": current_type_name},
        )

    async def async_step_reconfigure_cloud(self, user_input: dict | None = None):
        """Handle cloud API reconfiguration."""
        _LOGGER.debug("Reconfiguring to Cloud API")
        errors: dict[str, str] = {}

        if user_input is not None:
            sanitized_input = sanitize_user_input(user_input)
            _LOGGER.debug("Reconfigure cloud input: %s", sanitized_input)
            
            preferred_type = user_input.get("cloud_type", "auto")
            # Validate credentials
            error_code, system_type = await validate_credentials(user_input, preferred_type)
            
            if not error_code and system_type:
                # Auth success, update the entry
                user_input["connection_type"] = CONNECTION_TYPE_CLOUD
                user_input["system_type"] = system_type
                
                title = "Kronoterm Heat Pump (Cloud)"
                if system_type == "dhw":
                    title = "Kronoterm DHW (Water Cloud)"
                
                # Disable Modbus-only entities, re-enable Cloud entities
                await disable_mode_specific_entities(
                    self.hass, 
                    self.reconfig_entry.entry_id, 
                    "cloud"
                )
                await enable_mode_specific_entities(
                    self.hass,
                    self.reconfig_entry.entry_id,
                    "cloud"
                )
                
                return self.async_update_reload_and_abort(
                    self.reconfig_entry,
                    unique_id=cloud_config_unique_id(
                        user_input[CONF_USERNAME], system_type
                    ),
                    data=user_input,
                    title=title,
                )
            else:
                errors["base"] = error_code

        # Pre-fill current credentials if switching from cloud
        current_data = self.reconfig_entry.data
        default_username = current_data.get(CONF_USERNAME, "")
        default_password = current_data.get(CONF_PASSWORD, "")
        
        cloud_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=default_username): str,
            vol.Required(CONF_PASSWORD, default=default_password): str,
            vol.Required("cloud_type", default=current_data.get("cloud_type", "dhw")): vol.In({
                "cloud": "Heating heat pump",
                "dhw": "Sanitary water heat pump",
            }),
        })
        
        return self.async_show_form(
            step_id="reconfigure_cloud",
            data_schema=cloud_schema,
            errors=errors
        )

    async def async_step_reconfigure_modbus_transport(self, user_input: dict | None = None):
        """Select Modbus transport during reconfiguration."""
        current_data = self.reconfig_entry.data
        current_transport = current_data.get("transport", MODBUS_TRANSPORT_TCP)

        if user_input is not None:
            self.modbus_transport = user_input.get("transport", MODBUS_TRANSPORT_TCP)
            if self.modbus_transport == MODBUS_TRANSPORT_RTU:
                return await self.async_step_reconfigure_modbus_rtu()
            return await self.async_step_reconfigure_modbus_tcp()

        return self.async_show_form(
            step_id="reconfigure_modbus_transport",
            data_schema=get_modbus_transport_schema(current_transport),
        )

    async def async_step_reconfigure_modbus_tcp(self, user_input: dict | None = None):
        """Handle Modbus TCP reconfiguration."""
        _LOGGER.debug("Reconfiguring to Modbus TCP")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Reconfigure modbus TCP input: %s", user_input)
            user_input["transport"] = MODBUS_TRANSPORT_TCP
            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                await disable_mode_specific_entities(
                    self.hass,
                    self.reconfig_entry.entry_id,
                    "modbus"
                )
                await enable_mode_specific_entities(
                    self.hass,
                    self.reconfig_entry.entry_id,
                    "modbus"
                )

                return self.async_update_reload_and_abort(
                    self.reconfig_entry,
                    unique_id=modbus_config_unique_id(
                        MODBUS_TRANSPORT_TCP,
                        user_input[CONF_HOST],
                        user_input.get(CONF_PORT, 502),
                        user_input.get("unit_id", 20),
                    ),
                    data=user_input,
                    title="Kronoterm Heat Pump (Modbus)",
                )
            errors["base"] = error_code

        current_data = self.reconfig_entry.data
        return self.async_show_form(
            step_id="reconfigure_modbus_tcp",
            data_schema=get_modbus_tcp_schema(current_data),
            errors=errors,
        )

    async def async_step_reconfigure_modbus_rtu(self, user_input: dict | None = None):
        """Handle Modbus RTU reconfiguration."""
        _LOGGER.debug("Reconfiguring to Modbus RTU")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Reconfigure modbus RTU input: %s", user_input)
            user_input["transport"] = MODBUS_TRANSPORT_RTU
            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                await disable_mode_specific_entities(
                    self.hass,
                    self.reconfig_entry.entry_id,
                    "modbus"
                )
                await enable_mode_specific_entities(
                    self.hass,
                    self.reconfig_entry.entry_id,
                    "modbus"
                )

                return self.async_update_reload_and_abort(
                    self.reconfig_entry,
                    unique_id=modbus_config_unique_id(
                        MODBUS_TRANSPORT_RTU,
                        user_input["serial_port"],
                        0,
                        user_input.get("unit_id", 20),
                    ),
                    data=user_input,
                    title="Kronoterm Heat Pump (Modbus)",
                )
            errors["base"] = error_code

        current_data = self.reconfig_entry.data
        return self.async_show_form(
            step_id="reconfigure_modbus_rtu",
            data_schema=get_modbus_rtu_schema(current_data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry
    ) -> "KronotermOptionsFlowHandler":
        """Get the options flow for this integration."""
        return KronotermOptionsFlowHandler()

    async def async_step_reauth(self, entry_data: dict):
        """Start Cloud credential renewal after an authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None):
        """Validate replacement credentials and reload the Cloud entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        current_username = entry.data.get(CONF_USERNAME, "")
        preferred_type = entry.data.get("system_type", "cloud")

        if user_input is not None:
            effective_data = dict(entry.data)
            effective_data.update(user_input)
            error_code, system_type = await validate_credentials(
                effective_data, preferred_type
            )
            if not error_code and system_type:
                effective_data["connection_type"] = CONNECTION_TYPE_CLOUD
                effective_data["system_type"] = system_type
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=cloud_config_unique_id(
                        effective_data[CONF_USERNAME], system_type
                    ),
                    data=effective_data,
                )
            errors["base"] = error_code or "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=current_username
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class KronotermOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Handles the options flow for the Kronoterm integration.
    Allows updating credentials, scan interval, and other settings.
    """

    async def async_step_init(self, user_input: dict | None = None):
        """Handle the initial step of the options flow."""
        _LOGGER.debug("Starting options flow init step")
        errors: dict[str, str] = {}
        current_options = self.config_entry.options
        current_data = self.config_entry.data
        connection_type = current_data.get(
            "connection_type", CONNECTION_TYPE_CLOUD
        )
        legacy_minutes = current_options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )
        scan_interval_seconds = current_options.get(
            "scan_interval_seconds", legacy_minutes * 60
        )

        if connection_type == CONNECTION_TYPE_MODBUS:
            if user_input is not None:
                options = dict(current_options)
                options["scan_interval_seconds"] = user_input[
                    "scan_interval_seconds"
                ]
                options.pop("scan_interval", None)
                return self.async_create_entry(title="", data=options)

            options_schema = vol.Schema(
                {
                    vol.Required(
                        "scan_interval_seconds",
                        default=scan_interval_seconds,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
                }
            )
        else:
            username = current_options.get(
                CONF_USERNAME, current_data.get(CONF_USERNAME, "")
            )
            if user_input is not None:
                effective_data = dict(current_data)
                effective_data.update(current_options)
                effective_data[CONF_USERNAME] = user_input[CONF_USERNAME]
                if user_input.get(CONF_PASSWORD):
                    effective_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

                preferred_type = current_data.get("system_type", "cloud")
                error_code, system_type = await validate_credentials(
                    effective_data, preferred_type
                )
                if not error_code and system_type:
                    options = dict(current_options)
                    options.update(
                        {
                            CONF_USERNAME: effective_data[CONF_USERNAME],
                            CONF_PASSWORD: effective_data[CONF_PASSWORD],
                            "scan_interval_seconds": user_input[
                                "scan_interval_seconds"
                            ],
                        }
                    )
                    options.pop("scan_interval", None)
                    _LOGGER.debug(
                        "Cloud options saved: %s", sanitize_user_input(options)
                    )
                    return self.async_create_entry(title="", data=options)

                errors["base"] = error_code or "unknown"

            options_schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=username): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Required(
                        "scan_interval_seconds",
                        default=max(scan_interval_seconds, 30),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                }
            )

        return self.async_show_form(
            step_id="init", 
            data_schema=options_schema,
            errors=errors
        )

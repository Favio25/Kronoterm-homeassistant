import logging
import asyncio
import aiohttp  # Make sure aiohttp is imported at the top
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
# We no longer need async_get_clientsession
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT

from .const import (
    DOMAIN, 
    BASE_URL, 
    API_QUERIES_GET, 
    DEFAULT_SCAN_INTERVAL, 
    REQUEST_TIMEOUT
)

from .config_flow_modbus import (
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_MODBUS,
    validate_modbus_connection,
    get_connection_type_schema,
    get_modbus_schema,
)

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

async def validate_credentials(data: dict) -> str | None:
    """
    Validate the credentials by attempting a lightweight API call.
    Returns an error code string on failure, or None on success.
    
    Uses its own session to avoid cookie reuse from other instances.
    """
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    auth = aiohttp.BasicAuth(username, password)
    
    query_params = API_QUERIES_GET["info"]
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    # Create a new, temporary session that has no cookies
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                BASE_URL, 
                auth=auth, 
                params=query_params, 
                timeout=timeout
            ) as response:
                if response.status == 200:
                    _LOGGER.debug("Authentication successful")
                    return None  # Success
                if response.status == 401:
                    _LOGGER.warning("Authentication failed: Invalid username or password")
                    return "invalid_auth"
                
                _LOGGER.error("Authentication failed: HTTP %s", response.status)
                return "cannot_connect"

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Authentication failed: Connection error: %s", err)
            return "cannot_connect"
        except Exception as err:
            _LOGGER.error("Authentication failed: Unexpected error: %s", err, exc_info=True)
            return "unknown"


class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles the configuration flow for the Kronoterm integration.
    """
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.connection_type = None
        self.reconfig_entry = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initialized by the user - choose connection type."""
        _LOGGER.debug("Starting user step in KronotermConfigFlow")
        
        if user_input is not None:
            # Store connection type and move to appropriate step
            self.connection_type = user_input.get("connection_type", CONNECTION_TYPE_CLOUD)
            _LOGGER.debug("Connection type selected: %s", self.connection_type)
            
            if self.connection_type == CONNECTION_TYPE_MODBUS:
                return await self.async_step_modbus()
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
            
            # Validate credentials
            error_code = await validate_credentials(user_input)
            if not error_code:
                # Auth success, add connection type and create entry
                user_input["connection_type"] = CONNECTION_TYPE_CLOUD
                return self.async_create_entry(
                    title="Kronoterm Heat Pump (Cloud)", 
                    data=user_input
                )
            else:
                # Auth failed, set error and show form again
                errors["base"] = error_code

        cloud_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        
        return self.async_show_form(
            step_id="cloud", 
            data_schema=cloud_schema,
            errors=errors
        )

    async def async_step_modbus(self, user_input: dict | None = None):
        """Handle Modbus TCP configuration."""
        _LOGGER.debug("Starting Modbus TCP configuration step")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Modbus config received: %s", user_input)
            
            # Validate Modbus connection
            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                # Connection success, add connection type and create entry
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                return self.async_create_entry(
                    title="Kronoterm Heat Pump (Modbus)",
                    data=user_input
                )
            else:
                # Connection failed, set error and show form again
                errors["base"] = error_code

        return self.async_show_form(
            step_id="modbus",
            data_schema=get_modbus_schema(),
            errors=errors
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
                return await self.async_step_reconfigure_modbus()
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
            
            # Validate credentials
            error_code = await validate_credentials(user_input)
            if not error_code:
                # Auth success, update the entry
                user_input["connection_type"] = CONNECTION_TYPE_CLOUD
                self.hass.config_entries.async_update_entry(
                    self.reconfig_entry,
                    data=user_input,
                    title="Kronoterm Heat Pump (Cloud)"
                )
                # Reload the entry to apply changes
                await self.hass.config_entries.async_reload(self.reconfig_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            else:
                errors["base"] = error_code

        # Pre-fill current credentials if switching from cloud
        current_data = self.reconfig_entry.data
        default_username = current_data.get(CONF_USERNAME, "")
        default_password = current_data.get(CONF_PASSWORD, "")
        
        cloud_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=default_username): str,
            vol.Required(CONF_PASSWORD, default=default_password): str,
        })
        
        return self.async_show_form(
            step_id="reconfigure_cloud",
            data_schema=cloud_schema,
            errors=errors
        )

    async def async_step_reconfigure_modbus(self, user_input: dict | None = None):
        """Handle Modbus TCP reconfiguration."""
        _LOGGER.debug("Reconfiguring to Modbus TCP")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Reconfigure modbus input: %s", user_input)
            
            # Validate Modbus connection
            error_code = await validate_modbus_connection(user_input)
            if not error_code:
                # Connection success, update the entry
                user_input["connection_type"] = CONNECTION_TYPE_MODBUS
                self.hass.config_entries.async_update_entry(
                    self.reconfig_entry,
                    data=user_input,
                    title="Kronoterm Heat Pump (Modbus)"
                )
                # Reload the entry to apply changes
                await self.hass.config_entries.async_reload(self.reconfig_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            else:
                errors["base"] = error_code

        # Pre-fill current Modbus settings if available
        current_data = self.reconfig_entry.data
        schema_dict = {
            vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=current_data.get(CONF_PORT, 502)): int,
            vol.Required("unit_id", default=current_data.get("unit_id", 20)): int,
        }

        return self.async_show_form(
            step_id="reconfigure_modbus",
            data_schema=vol.Schema(schema_dict),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry
    ) -> "KronotermOptionsFlowHandler":
        """Get the options flow for this integration."""
        return KronotermOptionsFlowHandler()


class KronotermOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Handles the options flow for the Kronoterm integration.
    Allows updating credentials, scan interval, and other settings.
    """

    async def async_step_init(self, user_input: dict | None = None):
        """Handle the initial step of the options flow."""
        _LOGGER.debug("Starting options flow init step")
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate credentials, as they might have been changed
            # We no longer pass self.hass
            error_code = await validate_credentials(user_input)
            if not error_code:
                _LOGGER.debug("Options saved: %s", sanitize_user_input(user_input))
                # Save the validated input (including any new credentials)
                return self.async_create_entry(title="", data=user_input)
            else:
                _LOGGER.warning("Failed to save options: credentials invalid")
                errors["base"] = error_code
        
        # Get current values from options, falling back to data (for credentials)
        # or defaults (for other settings)
        current_options = self.config_entry.options
        current_data = self.config_entry.data
        
        username = current_options.get(CONF_USERNAME, current_data.get(CONF_USERNAME, ""))
        password = current_options.get(CONF_PASSWORD, current_data.get(CONF_PASSWORD, ""))
        scan_interval = current_options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

        # Build the schema with current values as defaults
        options_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=username): str,
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Optional(
                "scan_interval",
                default=scan_interval
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        })

        return self.async_show_form(
            step_id="init", 
            data_schema=options_schema,
            errors=errors
        )
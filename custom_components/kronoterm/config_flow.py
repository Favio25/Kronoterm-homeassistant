import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

logger = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 5

def sanitize_user_input(user_input: dict) -> dict:
    """
    Sanitizes user input by redacting sensitive information for logging purposes.

    Returns:
        A new dictionary where sensitive keys (username, password) are replaced with "[REDACTED]".
    """
    return {
        key: ("[REDACTED]" if key in ["password", "username"] else value)
        for key, value in user_input.items()
    }

class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles the configuration flow for the Kronoterm integration.
    
    This class manages the user interactions required to set up and configure
    the Kronoterm Heat Pump within Home Assistant.
    """
    VERSION = 1

    async def async_step_user(self, user_input: dict = None):
        """Handle a flow initialized by the user."""
        logger.debug("Starting user step in KronotermConfigFlow")
        if user_input is not None:
            # Log only the keys to avoid logging sensitive information.
            logger.debug("User input received with keys: %s", list(user_input.keys()))
            return self.async_create_entry(title="Kronoterm Heat Pump", data=user_input)

        # Show configuration form to the user without description_placeholders.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
                }
            )
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "KronotermOptionsFlowHandler":
        """Get the options flow for this integration."""
        return KronotermOptionsFlowHandler(config_entry)


class KronotermOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Handles the options flow for the Kronoterm integration.
    
    This class allows users to modify configuration options after the initial setup
    of the Kronoterm Heat Pump integration.
    """
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow handler."""
        self.config_entry = config_entry
        logger.info("KronotermOptionsFlowHandler initialized")

    async def async_step_init(self, user_input: dict = None):
        """Handle the initial step of the options flow."""
        logger.debug("Starting options flow init step")
        if user_input is not None:
            logger.debug("User input received in options flow with keys: %s", list(user_input.keys()))
            # Save updated options.
            return self.async_create_entry(title="", data=user_input)

        # Show the options form without description_placeholders.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=1, max=60)),
                }
            )
        )

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN


class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Validate and create entry
            return self.async_create_entry(title="Kronoterm Heat Pump", data=user_input)

        # Show configuration form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Optional("scan_interval", default=300): int,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KronotermOptionsFlowHandler(config_entry)


class KronotermOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Save updated options
            return self.async_create_entry(title="", data=user_input)

        # Show options form
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", 300),
                    ): int,
                }
            ),
        )

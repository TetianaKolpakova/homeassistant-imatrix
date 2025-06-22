from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
from .const import DOMAIN, API_BASE
import logging

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("email"): str,
    vol.Required("password"): str,
})

class IMatrixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            # Перевірка логіну
            try:
                session = aiohttp.ClientSession()
                async with session.post(
                    f"{API_BASE}/login",
                    json={
                        "email": user_input["email"],
                        "password": user_input["password"]
                    },
                    ssl=False,
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200 or "token" not in data:
                        _LOGGER.warning("Login failed: %s", data)
                        return self.async_show_form(
                            step_id="user",
                            data_schema=STEP_USER_DATA_SCHEMA,
                            errors={"base": "invalid_auth"}
                        )
            except Exception as e:
                _LOGGER.error("Connection error: %s", e)
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"}
                )
            finally:
                await session.close()

            return self.async_create_entry(
                title=user_input["email"],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

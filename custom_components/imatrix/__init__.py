import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, API_BASE

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    session = async_get_clientsession(hass)
    email = entry.data.get("email")
    password = entry.data.get("password")

    try:
        auth_response = await session.post(
            f"{API_BASE}/login",
            json={"email": email, "password": password},
            ssl=False
        )
        auth_data = await auth_response.json()
        token = auth_data.get("token")

        if not token:
            _LOGGER.error("❌ iMatrix login failed: %s", auth_data)
            return False

        # Ініціалізуємо зберігання, якщо не існує
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        # Зберігаємо дані цього конфіг-запису
        hass.data[DOMAIN][entry.entry_id] = {
            "session": session,
            "token": token,
        }

        _LOGGER.info("🔑 iMatrix login successful — token starts with: %s", token[:15])
        try:
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        except ValueError as e:
            _LOGGER.warning("⚠️ Platform already set up: %s", e)

        return True

    except Exception as e:
        _LOGGER.exception("💥 iMatrix: Error during login: %s", e)
        raise ConfigEntryNotReady from e

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return True

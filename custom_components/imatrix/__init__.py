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
        # Використовуємо функцію оновлення токена
        token = await _refresh_token(session, email, password)
        if not token:
            _LOGGER.error("❌ iMatrix login failed for user: %s", email)
            return False

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        hass.data[DOMAIN][entry.entry_id] = {
            "session": session,
            "token": token,
            "email": email,
            "password": password,
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

async def _refresh_token(session, email: str, password: str) -> str | None:
    """
    Виконує повторну авторизацію для отримання нового токена.
    """
    try:
        login_url = f"{API_BASE}/login"
        _LOGGER.debug("🔄 Refreshing token at: %s", login_url)
        resp = await session.post(login_url, json={"email": email, "password": password}, ssl=False)
        if resp.status != 200:
            _LOGGER.warning("⚠️ Login failed with HTTP %s", resp.status)
            return None
        data = await resp.json()
        token = data.get("token")
        if token:
            _LOGGER.info("🔐 Token successfully refreshed for user %s", email)
        else:
            _LOGGER.error("❌ Failed to retrieve token: %s", data)
        return token
    except Exception as e:
        _LOGGER.exception("💥 Error refreshing token: %s", e)
        return None
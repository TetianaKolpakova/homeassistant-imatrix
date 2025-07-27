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
    # Якщо інтеграція для цього entry вже налаштована
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        _LOGGER.warning("⚠️ Platform for %s already set up", entry.entry_id)
        return True

    session = async_get_clientsession(hass)
    email = entry.data.get("email")
    password = entry.data.get("password")

    try:
        login_url = f"{API_BASE}/login"
        _LOGGER.debug("🔑 Logging in to iMatrix API: %s", login_url)

        auth_response = await session.post(
            login_url,
            json={"email": email, "password": password},
            ssl=False
        )

        if auth_response.status == 401:
            _LOGGER.error("⛔ Unauthorized (401) on login. Reloading integration...")
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
            return False

        auth_data = await auth_response.json()
        token = auth_data.get("token")

        if not token:
            _LOGGER.error("❌ iMatrix login failed: %s", auth_data)
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
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

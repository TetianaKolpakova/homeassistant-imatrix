import logging
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfTemperature,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTime,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from .const import DOMAIN, API_BASE
from .units import resolve_unit

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not entry_data:
        _LOGGER.error("❌ No entry data for iMatrix entry_id %s", config_entry.entry_id)
        return

    session = entry_data.get("session")
    token = entry_data.get("token")
    headers = {"x-auth-token": token}
    entities_to_add = []

    try:
        things_url = f"{API_BASE}/things?page=1&per_page=100"
        _LOGGER.debug("🌐 Requesting iMatrix things from: %s", things_url)
        things_resp = await session.get(things_url, headers=headers, ssl=False)
        if things_resp.status == 401:
            _LOGGER.error("⛔ Unauthorized (401). Reloading iMatrix integration...")
            hass.async_create_task(hass.config_entries.async_reload(config_entry.entry_id))
            return

        things_data = await things_resp.json()
        things = things_data.get("list", [])
        _LOGGER.info("✅ Found %d things", len(things))

        for thing in things:
            sn = thing.get("sn")
            name = thing.get("name", f"Thing {sn}")
            firmware = thing.get("currentVersion")
            mac = thing.get("mac")
            product_url = f"{API_BASE}/things/{sn}/product"
            prod_resp = await session.get(product_url, headers=headers, ssl=False)
            if prod_resp.status == 401:
                _LOGGER.error("⛔ Unauthorized (401) when requesting product info. Reloading integration...")
                hass.async_create_task(hass.config_entries.async_reload(config_entry.entry_id))
                return

            prod_data = await prod_resp.json()
            short_name = prod_data.get("shortName") or "Unknown"
            device_icon = prod_data.get("iconUrl")
            if not device_icon or not device_icon.startswith("http"):
                device_icon = None

            device_info = DeviceInfo(
                identifiers={(DOMAIN, str(sn))},
                name=name,
                manufacturer="iMatrix",
                model=short_name,
                sw_version=firmware,
                serial_number=str(sn),
                connections={("mac", mac)},
                configuration_url=f"https://app.imatrixsys.com/things/{sn}",
            )

            # Last seen
            last_url = f"{API_BASE}/things/{sn}/sensors/last"
            last_resp = await session.get(last_url, headers=headers, ssl=False)
            if last_resp.status == 401:
                _LOGGER.error("⛔ Unauthorized (401) when requesting last sensor data. Reloading integration...")
                hass.async_create_task(hass.config_entries.async_reload(config_entry.entry_id))
                return

            last_json = await last_resp.json()
            sensors_values = last_json.get(str(sn), {}).get("sensorsData", {})
            last_seen_ts = last_json.get(str(sn), {}).get("lastSeen")

            if last_seen_ts:
                entities_to_add.append(IMatrixLastSeenSensor(sn, name, device_info, last_seen_ts))

            # Sensors
            sensors_url = f"{API_BASE}/things/{sn}/sensors"
            sensors_resp = await session.get(sensors_url, headers=headers, ssl=False)
            if sensors_resp.status == 401:
                _LOGGER.error("⛔ Unauthorized (401) when requesting sensors list. Reloading integration...")
                hass.async_create_task(hass.config_entries.async_reload(config_entry.entry_id))
                return

            sensors_list = await sensors_resp.json()
            for sensor_meta in sensors_list:
                sid = sensor_meta.get("id")
                unit = sensor_meta.get("units")
                if str(sid) not in sensors_values:
                    continue
                value = sensors_values[str(sid)].get("value")
                if unit == "Tamper":
                    entities_to_add.append(
                        IMatrixTamperBinarySensorEntity(
                            session, headers, sensor_meta, sn, name, device_info, value
                        )
                    )
                else:
                    entities_to_add.append(
                        IMatrixSensorEntity(
                            session, headers, sensor_meta, sn, name, device_info, value
                        )
                    )

    except Exception as e:
        _LOGGER.exception("💥 Error in setup: %s", e)

    if entities_to_add:
        async_add_entities(entities_to_add)


class IMatrixLastSeenSensor(SensorEntity):
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, thing_sn, thing_name, device_info, ts):
        self._thing_sn = thing_sn
        self._thing_name = thing_name
        self._device_info = device_info
        self._ts = ts
        self._attr_name = f"{thing_name}: Last Seen"
        self._attr_unique_id = f"imatrix_{thing_sn}_last_seen"

    @property
    def native_value(self):
        return datetime.fromtimestamp(self._ts / 1000, tz=timezone.utc)

    @property
    def device_info(self):
        return self._device_info


class IMatrixTamperBinarySensorEntity(BinarySensorEntity):
    _attr_should_poll = True
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, session, headers, meta, sn, thing, info, value=None):
        self._session = session
        self._headers = headers
        self._sensor_meta = meta
        self._sn = sn
        self._thing = thing
        self._device_info = info
        self._value = float(value)
        self._sensor_id = meta.get("id")
        self._name = meta.get("name")

    @property
    def name(self):
        return f"{self._thing}: {self._name}"

    @property
    def unique_id(self):
        return f"imatrix_{self._sn}_{self._sensor_id}"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.TAMPER

    @property
    def is_on(self):
        return self._value == 0.0

    @property
    def device_info(self):
        return self._device_info

    async def async_update(self):
        try:
            url = f"{API_BASE}/things/{self._sn}/sensors/last"
            resp = await self._session.get(url, headers=self._headers, ssl=False)
            if resp.status == 401:
                _LOGGER.error("⛔ Unauthorized (401) while updating tamper sensor %s. Reloading integration...", self.name)
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.platform.config_entry.entry_id)
                )
                return
            data = await resp.json()
            raw = data.get(str(self._sn), {}).get("sensorsData", {}).get(str(self._sensor_id), {}).get("value")
            self._value = float(raw)
        except Exception as e:
            _LOGGER.warning("⚠️ Could not update tamper sensor %s: %s", self.name, e)


class IMatrixSensorEntity(SensorEntity):
    _attr_should_poll = True

    def __init__(self, session, headers, meta, sn, thing, info, value=None):
        self._session = session
        self._headers = headers
        self._sensor_meta = meta
        self._sn = sn
        self._thing = thing
        self._device_info = info
        self._value = value
        self._sensor_id = meta.get("id")
        self._name = meta.get("name")
        self._unit_resolution = resolve_unit(self._name, meta.get("units"))
        resolution = self._unit_resolution
        self._attr_native_unit_of_measurement = resolution.unit
        self._attr_device_class = (
            SensorDeviceClass(resolution.device_class) if resolution.device_class else None
        )
        self._attr_extra_state_attributes = {
            "api_units": meta.get("units"),
            "unit_resolution": resolution.source,
        }
        if resolution.source in ("conflict", "unknown"):
            _LOGGER.warning("Unsupported unit for %s: %r (%s)",
                            self.name, meta.get("units"), resolution.source)
        elif resolution.source == "sensor_name":
            _LOGGER.debug("Using sensor profile for %s; API unit: %r",
                          self.name, meta.get("units"))
        if resolution.kind == "voltage":
            self._attr_icon = "mdi:sine-wave"
        elif resolution.kind == "duration":
            self._attr_icon = "mdi:clock-outline"
        elif resolution.kind == "count" and (self._name or "").casefold().startswith("open"):
            self._attr_icon = "mdi:door-open"
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if resolution.supported else None
        )

    @property
    def name(self):
        return f"{self._thing}: {self._name}"

    @property
    def unique_id(self):
        return f"imatrix_{self._sn}_{self._sensor_id}"

    @property
    def native_value(self):
        try:
            val = float(self._value)
        except Exception:
            return None
        resolution = self._unit_resolution
        if not resolution.supported:
            return None
        val = val * resolution.scale + resolution.offset
        if resolution.kind in ("duration", "count"):
            return round(val)
        if resolution.kind == "voltage":
            return round(val, 2)
        if resolution.kind == "angle":
            return round(val, 6)
        return round(val, 1)

    @property
    def device_info(self):
        return self._device_info

    async def async_update(self):
        try:
            url = f"{API_BASE}/things/{self._sn}/sensors/last"
            resp = await self._session.get(url, headers=self._headers, ssl=False)
            if resp.status == 401:
                _LOGGER.error("⛔ Unauthorized (401) while updating %s. Reloading integration...", self.name)
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.platform.config_entry.entry_id)
                )
                return
            data = await resp.json()
            raw_val = data.get(str(self._sn), {}).get("sensorsData", {}).get(str(self._sensor_id), {}).get("value")
            self._value = raw_val
        except Exception as e:
            _LOGGER.warning("⚠️ Could not update sensor %s: %s", self.name, e)

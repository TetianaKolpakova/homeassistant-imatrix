import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, UnitOfTemperature, UnitOfElectricPotential, UnitOfPressure, UnitOfTime
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from .const import DOMAIN, API_BASE

_LOGGER = logging.getLogger(__name__)

# Map units reported by API to Home Assistant units
UNIT_MAP = {
    "Deg. C": UnitOfTemperature.CELSIUS,
    "%RH": PERCENTAGE,
    "kPa": UnitOfPressure.KPA,
    "Volts": UnitOfElectricPotential.VOLT,
    "V": UnitOfElectricPotential.VOLT,
    "Bps": "Bps",
    "bps": "bps",
    "dB": SIGNAL_STRENGTH_DECIBELS,
    "Level": PERCENTAGE,
    "Seconds": UnitOfTime.SECONDS,
    "s": UnitOfTime.SECONDS,
    "Thing(s)": None,
    "Count": None,
}

# Map units to sensor device classes
DEVICE_CLASS_MAP = {
    "Deg. C": SensorDeviceClass.TEMPERATURE,
    "%RH": SensorDeviceClass.HUMIDITY,
    "kPa": SensorDeviceClass.PRESSURE,
    "dB": SensorDeviceClass.SIGNAL_STRENGTH,
    "Level": SensorDeviceClass.BATTERY,
    # "Seconds" and "Volts" deliberately omitted to avoid UI formatting issues
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info("🔄 Starting iMatrix sensor setup")
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not entry_data:
        _LOGGER.error("❌ No entry data for iMatrix entry_id %s", config_entry.entry_id)
        return

    session = entry_data["session"]
    token = entry_data["token"]
    headers = {"x-auth-token": token}
    entities_to_add = []

    try:
        things_url = f"{API_BASE}/things?page=1&per_page=100"
        _LOGGER.debug("Requesting things from %s", things_url)
        resp = await session.get(things_url, headers=headers, ssl=False)
        data = await resp.json()
        things = data.get("list", [])
        _LOGGER.info("✅ Found %d things", len(things))

        for thing in things:
            sn = thing.get("sn")
            name = thing.get("name", f"Thing {sn}")
            firmware = thing.get("currentVersion")
            product_url = f"{API_BASE}/things/{sn}/product"
            _LOGGER.debug("Requesting product info from %s", product_url)
            prod_resp = await session.get(product_url, headers=headers, ssl=False)
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
            )

            last_url = f"{API_BASE}/things/{sn}/sensors/last"
            _LOGGER.debug("Requesting last sensor data from %s", last_url)
            last_resp = await session.get(last_url, headers=headers, ssl=False)
            last_json = await last_resp.json()
            sensors_values = last_json.get(str(sn), {}).get("sensorsData", {})

            sensors_url = f"{API_BASE}/things/{sn}/sensors"
            _LOGGER.debug("Requesting sensors from %s", sensors_url)
            sensors_resp = await session.get(sensors_url, headers=headers, ssl=False)
            sensors_list = await sensors_resp.json()

            for sensor_meta in sensors_list:
                unit = sensor_meta.get("units")
                _LOGGER.debug("Sensor %s unit reported as '%s'", sensor_meta.get("name"), unit)
                sid = sensor_meta.get("id")
                if str(sid) not in sensors_values:
                    continue
                value = sensors_values[str(sid)].get("value")
                if unit == "Tamper":
                    ent = IMatrixTamperBinarySensorEntity(
                        session, headers, sensor_meta, sn,
                        name, device_info, hass, device_icon, value
                    )
                else:
                    ent = IMatrixSensorEntity(
                        session, headers, sensor_meta, sn,
                        name, device_info, hass, device_icon, value
                    )
                entities_to_add.append(ent)
    except Exception as e:
        _LOGGER.exception("💥 Error in setup: %s", e)

    if entities_to_add:
        _LOGGER.info("Adding %d entities", len(entities_to_add))
        async_add_entities(entities_to_add)


class IMatrixTamperBinarySensorEntity(BinarySensorEntity):
    _attr_should_poll = True

    def __init__(self, session, headers, meta, sn, thing, info, hass, icon=None, value=None):
        self._session = session
        self._headers = headers
        self._sensor_meta = meta
        self._sn = sn
        self._thing = thing
        self._device_info = info
        self._value = float(value)
        self._icon = icon
        self._sensor_id = meta.get("id")
        self._name = meta.get("name")
        self._attr_icon = "mdi:toggle-switch"

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
            data = await resp.json()
            self._value = float(data.get(str(self._sn), {}).get("sensorsData", {}).get(str(self._sensor_id), {}).get("value"))
        except Exception:
            pass


class IMatrixSensorEntity(SensorEntity):
    _attr_should_poll = True

    def __init__(self, session, headers, meta, sn, thing, info, hass, icon=None, value=None):
        self._session = session
        self._headers = headers
        self._sensor_meta = meta
        self._sn = sn
        self._thing = thing
        self._device_info = info
        self._value = value
        self._icon = icon
        self._sensor_id = meta.get("id")
        self._name = meta.get("name")
        self._unit = meta.get("units")

        self._attr_native_unit_of_measurement = UNIT_MAP.get(self._unit)
        if self._unit not in ("Seconds", "s", "Volts", "V"):
            self._attr_device_class = DEVICE_CLASS_MAP.get(self._unit)
        if self._unit in ("Volts", "V"):
            self._attr_icon = "mdi:sine-wave"
        elif self._unit in ("Seconds", "s"):
            self._attr_icon = "mdi:clock-outline"
        elif self._unit in ("Count",) and self._name.startswith("Open"):
            self._attr_icon = "mdi:door-open"

        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = self.native_value

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
        _LOGGER.debug("Rounding '%s' value=%s unit=%s", self.name, val, self._unit)
        if self._unit in ("Seconds", "s", "Count", "Thing(s)"):
            return round(val)
        elif self._unit in ("Volts", "V"):
            return round(val, 2)
        return round(val, 1)

    @property
    def device_info(self):
        return self._device_info

    async def async_update(self):
        try:
            url = f"{API_BASE}/things/{self._sn}/sensors/last"
            resp = await self._session.get(url, headers=self._headers, ssl=False)
            data = await resp.json()
            self._value = data.get(str(self._sn), {}).get("sensorsData", {}).get(str(self._sensor_id), {}).get("value")
            self._attr_native_value = self.native_value
        except Exception:
            pass

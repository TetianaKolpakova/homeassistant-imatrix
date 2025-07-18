# iMatrix Integration for Home Assistant

![iMatrix Logo](https://imatrixsys.com/wp-content/uploads/2020/12/Logo-No-Slogan.png)

## Overview

The **iMatrix Integration** is a custom component for Home Assistant that connects to [iMatrix Systems](https://imatrixsys.com/), a US-based provider of smart sensors and wireless gateways for environmental monitoring, industrial IoT, agriculture, and more.

iMatrix offers a wide range of sensors such as:

- Temperature and humidity sensors
- Air quality and barometric pressure sensors
- Contact (door open/close) and motion detectors
- Battery-powered and BLE-enabled sensors
- Micro and Sentry gateway devices

🛒 [iMatrix Shop](https://shop.imatrixsys.com/) /  🛒 [iMatrix Sensors on Amazon](https://www.amazon.com/stores/page/D67B92B5-2D7F-4358-B2A4-A69CD325ECE5)

## Features

This integration allows you to:

- 🔐 Log in to your [iMatrix Cloud](https://app.imatrixsys.com/) account
- 📡 Discover all registered devices
- 📈 Automatically fetch all active sensors per device
- 🔁 Poll sensor readings every 30 seconds
- 🧠 Display sensor states with correct units and formatting
- ✅ Visualize device model, firmware, and serial in the UI
- 🔔 Support binary tamper sensors (pressed/released)
- 🌐 Display icons per unit type and per sensor name (e.g., door icons for open counters)
- 🔄 Automatically refresh authentication token if it expires

## Security & Credentials

For authentication, the integration requires your **email** and **password** for the iMatrix Cloud. These credentials are:
- **Stored only in Home Assistant’s internal memory** (inside `hass.data`) and never transmitted to any third party.
- **Used exclusively to request a new token** from `https://api.imatrixsys.com/api/v1/login` when the current token expires.
- Not saved in plain text on disk, except as part of the Home Assistant configuration entry (encrypted by HA's internal mechanisms).

> **Note:** Your password is never sent to any location except iMatrix's official API endpoint, and only for the purpose of generating a new token.

## Supported Devices:
- [Micro Gateway](https://imatrixsys.com/micro-gateway/)
- [NEO-1](https://imatrixsys.com/neo-1/)
- [NEO-1P](https://imatrixsys.com/neo-1p/)
- [NEO-1D](https://imatrixsys.com/neo-1d/)
- [NEO-1DP](https://imatrixsys.com/neo-1dp/)
~~- [Sentry-1](https://imatrixsys.com/sentry-1/)~~ (needs more testing)

Supported sensor types include:

- Temperature (`°C`)
- Humidity (`%`)
- Pressure (`kPa`)
- Voltage (`V`)
- Duration (`s`)
- Counters (`Count`)
- Connected Devices  (`Thing(s)`)

## Manual Installation

1. 📁 Copy the entire custom_components/imatrix/ directory to your server's <config>/custom_components:
    ```
    /config/custom_components/imatrix/
    ```

2. 🔧 Restart Home Assistant.

3. ➕ Go to **Settings > Devices & Services > Add Integration** and choose **iMatrix Integration**.

4. 🔑 Enter your email and password for the iMatrix Cloud.

## Configuration

This integration supports configuration via UI only (Config Flow). No YAML configuration required.

## Localization

Login form available in English and Ukrainian.

## Known Limitations

- Requires an active iMatrix Cloud account
- Sensors without recent data are not displayed
- Data is fetched from the `sensors/last` endpoint

## License

MIT License © 2025 — @TetianaKolpakova

---

🔗 Learn more at [https://imatrixsys.com](https://imatrixsys.com)

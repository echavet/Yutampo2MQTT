# Yutampo HA Addon

![License](https://img.shields.io/github/license/echavet/yutampo_ha_addon)  
![GitHub Issues](https://img.shields.io/github/issues/echavet/yutampo_ha_addon)  
![GitHub Stars](https://img.shields.io/github/stars/echavet/yutampo_ha_addon)

A Home Assistant Add-on to integrate Yutampo water heaters (CSNet Manager) with Home Assistant via MQTT, enabling seamless remote monitoring and control of temperature and operating modes.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Add-on Installation](#add-on-installation)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

- **Seamless Integration**: Control and monitor your Yutampo water heater directly from Home Assistant.
- **MQTT Discovery**: Automatically discovers devices and creates `climate` entities in Home Assistant.
- **Temperature Control**: Adjust the setpoint temperature remotely via Home Assistant.
- **Mode Control**: Toggle between `heat` and `off` modes using Home Assistant.
- **Real-time Updates**: Periodically fetches device states (temperature, mode, operation status) and updates Home Assistant.
- **Bidirectional Sync**: Changes made via the CSNet Manager app are reflected in Home Assistant, and vice versa.
- **Detailed Status**: Reports `hvac_action` (e.g., `idle`, `heating`, `off`) and custom operation labels for advanced monitoring.

## Prerequisites

- A running instance of **Home Assistant** with the MQTT integration configured (e.g., Mosquitto broker).
- A **Yutampo water heater** connected to the CSNet Manager platform.
- Valid credentials (username and password) for the CSNet Manager website.
- Docker (if installing manually outside of Home Assistant add-ons).

## Installation

### Add-on Installation (Recommended)

1. **Add the Repository**:
   - In Home Assistant, go to **Settings > Add-ons > Add-on Store**.
   - Click the three dots (`...`) in the top-right corner and select **Repositories**.
   - Add this repository URL: `https://github.com/echavet/yutampo_ha_addon`.
   - Click **Add** and wait for the repository to load.

2. **Install the Add-on**:
   - Find **Yutampo HA Addon** in the list of add-ons.
   - Click **Install** and wait for the process to complete.

3. **Configure the Add-on**:
   - Go to the **Configuration** tab of the add-on.
   - Set your CSNet Manager credentials (`username` and `password`) and other options (see [Configuration](#configuration)).
   - Save the configuration.

4. **Start the Add-on**:
   - Go to the **Info** tab and click **Start**.
   - Check the **Log** tab to ensure the add-on starts without errors.

### Manual Installation (Advanced)

For users who prefer running the add-on outside of Home Assistant’s add-on system:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/echavet/yutampo_ha_addon.git
   cd yutampo_ha_addon
   ```

2. **Install Dependencies**:
   Ensure you have Python 3.8+ installed, then install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**:
   Set the MQTT environment variables (as expected by the `run.sh` script):
   ```bash
   export MQTTHOST="your-mqtt-broker-host"
   export MQTTPORT="1883"
   export MQTTUSER="your-mqtt-username"
   export MQTTPASSWORD="your-mqtt-password"
   ```

4. **Configure Options**:
   Create a `/data/options.json` file with your CSNet Manager credentials:
   ```json
   {
     "username": "your_csnetmanager_username",
     "password": "your_csnetmanager_password",
     "scan_interval": 30
   }
   ```

5. **Run the Add-on**:
   Execute the main script:
   ```bash
   python3 main.py
   ```

## Configuration

The add-on requires a configuration file (`/data/options.json`) with the following options:

| Option            | Description                                      | Default   | Required |
|-------------------|--------------------------------------------------|-----------|----------|
| `username`        | Your CSNet Manager username                     | -         | Yes      |
| `password`        | Your CSNet Manager password                     | -         | Yes      |
| `scan_interval`   | Interval (in seconds) to fetch device updates   | 300       | No       |

### Example Configuration

```json
{
  "username": "your_csnetmanager_username",
  "password": "your_csnetmanager_password",
  "scan_interval": 30
}
```

### Environment Variables (for Manual Installation)

The MQTT broker settings are sourced from environment variables (set by `run.sh` in Home Assistant):

| Variable         | Description                          | Default   | Required |
|------------------|--------------------------------------|-----------|----------|
| `MQTTHOST`       | MQTT broker host                    | -         | Yes      |
| `MQTTPORT`       | MQTT broker port                    | 1883      | No       |
| `MQTTUSER`       | MQTT broker username                | -         | Yes      |
| `MQTTPASSWORD`   | MQTT broker password                | -         | Yes      |

## Usage

1. **Start the Add-on**:
   - If installed as a Home Assistant add-on, start it from the **Info** tab.
   - If running manually, execute `python3 main.py` as described above.

2. **Monitor Logs**:
   - Check the logs in the Home Assistant Add-on interface or in your terminal.
   - Look for messages indicating successful authentication, MQTT connection, and device discovery.

3. **Home Assistant Integration**:
   - Once running, the add-on will publish MQTT Discovery messages, creating `climate` entities in Home Assistant (e.g., `climate.4103`).
   - You can control the water heater (mode and temperature) directly from the Home Assistant UI.
   - Changes made via the CSNet Manager app will also be reflected in Home Assistant after the next update (based on `scan_interval`).

4. **Logbook**:
   - Changes to mode (`off` → `heat`) and action (`idle`, `heating`) are logged in the Home Assistant Logbook.
   - Temperature changes (setpoint and current) are published as attributes and can be viewed in the entity details. To log temperature changes in the Logbook, additional customization may be required (e.g., using a `state_topic`).

## Troubleshooting

- **Authentication Failure**:
  - Ensure your CSNet Manager `username` and `password` are correct in `/data/options.json`.
  - Check the logs for HTTP errors (e.g., `403 Forbidden`) and verify internet connectivity.

- **MQTT Connection Issues**:
  - Verify that your MQTT broker (e.g., Mosquitto) is running and accessible.
  - Ensure the environment variables (`MQTTHOST`, `MQTTUSER`, etc.) are correctly set.

- **No Devices in Home Assistant**:
  - Confirm that the add-on is publishing MQTT Discovery messages (check logs for `Configuration MQTT Discovery publiée` entries).
  - Restart Home Assistant after starting the add-on to trigger MQTT Discovery.

- **Logbook Issues**:
  - If temperature changes are not appearing in the Logbook, verify that `state_topic` is correctly published and that Home Assistant is configured to log these changes.

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit them (`git commit -am 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request with a detailed description of your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **xAI**: For providing assistance in building and debugging this add-on.
- **Home Assistant Community**: For their amazing platform and MQTT integration.
- **Yutampo/CSNet Manager**: For providing the API that makes this integration possible.

---

### Notes on the README

- **Your GitHub Username**: I’ve replaced `USERNAME` with `echavet` in the URLs and badges.
- **Markdown Formatting**: Now properly formatted with headers, lists, tables, and code blocks for readability.
- **Flexibility**: If you want to add more details (e.g., screenshots of the integration in HA, specific examples of logbook entries, or badges for build status), let me know!
- **License**: I assumed MIT License, but if you prefer another license (e.g., GPL), let me know, and I’ll update the badge and section.

Let me know if you want any adjustments or additions to this `README.md`! 😊 Now that the core functionality is rock-solid, it’s a great time to showcase it properly on GitHub. What do you think?
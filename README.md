# Yutampo2MQTT Home Assistant Add-on

## Overview

The Yutampo2MQTT add-on integrates Yutampo water heaters with Home Assistant via the CSNetManager API. It provides MQTT-based control, automation, and weather-based temperature regulation for optimal energy efficiency.

## Features

- **MQTT Integration**: Publishes device states and receives commands via MQTT.
- **CSNetManager API**: Fetches device data and sends commands to Yutampo devices.
- **Weather-Based Automation**: Adjusts temperature setpoints based on weather forecasts (requires a weather entity).
- **Customizable Regulation**: Configurable setpoint, amplitude, and heating duration for temperature regulation.
- **MQTT Discovery**: Automatically creates climate entities in Home Assistant.
- **Availability Handling**: Publishes `online`/`offline` status via MQTT Last Will and Testament (LWT).

## Installation

1. Add the repository to Home Assistant:
   - Go to **Settings > Add-ons > Add-on Store**.
   - Click the three dots in the top-right corner and select **Repositories**.
   - Add: `https://github.com/echavet/Yutampo2MQTT`.
2. Install the add-on:
   - Find **Yutampo2MQTT HA Addon** in the Add-on Store.
   - Click **Install** and wait for the installation to complete.
3. Configure the add-on:
   - Open the add-on configuration and set your CSNetManager `username` and `password`.
   - Optionally configure MQTT settings, weather entity, setpoint, amplitude, and heating duration.
4. Start the add-on:
   - Enable **Start on boot** and **Auto update** if desired.
   - Click **Start**.

## Configuration Options

| Option                  | Description                                      | Default            |
|-------------------------|--------------------------------------------------|--------------------|
| `username`             | CSNetManager username                           | Required           |
| `password`             | CSNetManager password                           | Required           |
| `scan_interval`        | Device state update interval (seconds)          | 300                |
| `setpoint`             | Base temperature setpoint (°C)                  | 50.0               |
| `default_hottest_hour` | Default hottest hour of the day (0-23)          | 15.0               |
| `heating_duration_hours` | Heating duration centered on hottest hour (hours) | 6.0            |
| `regulation_amplitude` | Temperature amplitude for regulation (°C)       | 8.0 (disabled if 0) |
| `weather_entity`       | Weather entity for forecast-based regulation    | Optional           |
| `log_level`            | Logging level (VERBOSE, DEBUG, INFO, WARNING, ERROR) | DEBUG         |
| `mqtt_host`            | MQTT broker host                                | `<auto_detect>`    |
| `mqtt_port`            | MQTT broker port                                | `<auto_detect>`    |
| `mqtt_user`            | MQTT username                                   | `<auto_detect>`    |
| `mqtt_password`        | MQTT password                                   | `<auto_detect>`    |

## Usage

- **Climate Entities**: Each Yutampo device appears as a climate entity in Home Assistant, allowing mode control (`off`/`heat`) and temperature setpoint adjustments.
- **Automation**: The add-on adjusts the temperature setpoint based on the hottest hour of the day (from weather forecasts or `default_hottest_hour`) within a configurable heating duration.
  - **Automatic Regulation**: Enabled by default with `regulation_amplitude` set to 8°C. Disabled if set to 0.
- **Input Numbers**: Adjust `yutampo_amplitude` and `yutampo_heating_duration` via Home Assistant to fine-tune the regulation.

## Troubleshooting

- **Entities not unavailable when add-on stops**:
  - Ensure MQTT Last Will and Testament (LWT) is configured correctly in `MqttHandler`.
  - Check that the broker (Mosquitto) supports LWT and that the `yutampo/status` topic is published.
- **No weather-based regulation**:
  - Verify that `weather_entity` is set to a valid weather entity providing hourly forecasts.
  - Ensure `regulation_amplitude` is set to a positive value to enable regulation.
- **Logs not visible**:
  - Check the add-on logs in Home Assistant UI.
  - Adjust `log_level` to `DEBUG` or `VERBOSE` for more details.

## Contributing

Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/echavet/Yutampo2MQTT).

## License

This add-on is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Maintainer

Eric Chavet <echavet@gmail.com>

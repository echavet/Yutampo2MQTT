# Yutampo2MQTT HA Addon

![License](https://img.shields.io/github/license/echavet/Yutampo2MQTT)  
![GitHub Issues](https://img.shields.io/github/issues/echavet/Yutampo2MQTT)  
![GitHub Stars](https://img.shields.io/github/stars/echavet/Yutampo2MQTT)

A Home Assistant Add-on to integrate Yutampo water heaters (CSNet Manager) with Home Assistant via MQTT, enabling seamless remote monitoring and control of temperature and operating modes, with advanced automation features.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Add-on Installation](#add-on-installation)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Advanced Features](#advanced-features)
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
- **Advanced Automation**: Includes a virtual thermostat and customizable seasonal presets for energy optimization (see [Advanced Features](#advanced-features)).

## Prerequisites

- A running instance of **Home Assistant** with the MQTT integration configured (e.g., Mosquitto broker).
- A **Yutampo water heater** connected to the CSNet Manager platform.
- Valid credentials (username and password) for the CSNet Manager website.
- Docker (if installing manually outside of Home Assistant add-ons).
- A weather entity (e.g., `weather.home`) in Home Assistant for advanced automation features.

## Installation

### Add-on Installation (Recommended)

1. **Add the Repository**:

   - In Home Assistant, go to **Settings > Add-ons > Add-on Store**.
   - Click the three dots (`...`) in the top-right corner and select **Repositories**.
   - Add this repository URL: `https://github.com/echavet/Yutampo2MQTT`.
   - Click **Add** and wait for the repository to load.

2. **Install the Add-on**:

   - Find **Yutampo2MQTT HA Addon** in the list of add-ons.
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
   git clone https://github.com/echavet/Yutampo2MQTT.git
   cd Yutampo2MQTT
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
   Create a `/data/options.json` file with your CSNet Manager credentials and optional preset configurations:

   ```json
   {
     "username": "your_csnetmanager_username",
     "password": "your_csnetmanager_password",
     "scan_interval": 300,
     "presets": [
       {
         "name": "Hiver",
         "target_temperature": 50,
         "target_temperature_low": 45,
         "target_temperature_high": 55,
         "duration": 6
       },
       {
         "name": "Printemps/Automne",
         "target_temperature": 45,
         "target_temperature_low": 41,
         "target_temperature_high": 49,
         "duration": 5
       },
       {
         "name": "Été",
         "target_temperature": 40,
         "target_temperature_low": 37,
         "target_temperature_high": 43,
         "duration": 4
       }
     ]
   }
   ```

5. **Run the Add-on**:
   Execute the main script:
   ```bash
   python3 main.py
   ```

## Configuration

The add-on requires a configuration file (`/data/options.json`) with the following options:

| Option          | Description                                                            | Default   | Required |
| --------------- | ---------------------------------------------------------------------- | --------- | -------- |
| `username`      | Your CSNet Manager username                                            | -         | Yes      |
| `password`      | Your CSNet Manager password                                            | -         | Yes      |
| `scan_interval` | Interval (in seconds) to fetch device updates                          | 300       | No       |
| `presets`       | List of seasonal presets (see [Advanced Features](#advanced-features)) | See below | No       |

### Default Presets

If not specified, the following default presets are used:

```json
[
  {
    "name": "Hiver",
    "target_temperature": 50,
    "target_temperature_low": 45,
    "target_temperature_high": 55,
    "duration": 6
  },
  {
    "name": "Printemps/Automne",
    "target_temperature": 45,
    "target_temperature_low": 41,
    "target_temperature_high": 49,
    "duration": 5
  },
  {
    "name": "Été",
    "target_temperature": 40,
    "target_temperature_low": 37,
    "target_temperature_high": 43,
    "duration": 4
  }
]
```

### Example Configuration

```json
{
  "username": "your_csnetmanager_username",
  "password": "your_csnetmanager_password",
  "scan_interval": 300,
  "presets": [
    {
      "name": "Hiver",
      "target_temperature": 50,
      "target_temperature_low": 45,
      "target_temperature_high": 55,
      "duration": 6
    },
    {
      "name": "Printemps/Automne",
      "target_temperature": 45,
      "target_temperature_low": 41,
      "target_temperature_high": 49,
      "duration": 5
    },
    {
      "name": "Été",
      "target_temperature": 40,
      "target_temperature_low": 37,
      "target_temperature_high": 43,
      "duration": 4
    }
  ]
}
```

### Environment Variables (for Manual Installation)

The MQTT broker settings are sourced from environment variables (set by `run.sh` in Home Assistant):

| Variable       | Description          | Default | Required |
| -------------- | -------------------- | ------- | -------- |
| `MQTTHOST`     | MQTT broker host     | -       | Yes      |
| `MQTTPORT`     | MQTT broker port     | 1883    | No       |
| `MQTTUSER`     | MQTT broker username | -       | Yes      |
| `MQTTPASSWORD` | MQTT broker password | -       | Yes      |

## Usage

1. **Start the Add-on**:

   - If installed as a Home Assistant add-on, start it from the **Info** tab.
   - If running manually, execute `python3 main.py` as described above.

2. **Monitor Logs**:

   - Check the logs in the Home Assistant Add-on interface or in your terminal.
   - Look for messages indicating successful authentication, MQTT connection, and device discovery.

3. **Home Assistant Integration**:

   - Once running, the add-on will publish MQTT Discovery messages, creating `climate` entities (e.g., `climate.4103`) and an `input_select` entity for presets (e.g., `input_select.yutampo_season_preset`).
   - Control the water heater (mode and temperature) directly from the Home Assistant UI.
   - Changes made via the CSNet Manager app will be reflected in Home Assistant after the next update (based on `scan_interval`).

4. **Logbook**:
   - Changes to mode (`off` → `heat`) and action (`idle`, `heating`) are logged in the Home Assistant Logbook.
   - Temperature changes (setpoint and current) are published as attributes and can be viewed in the entity details. To log temperature changes in the Logbook, additional customization may be required (e.g., using a `state_topic`).

## Advanced Features

This add-on includes advanced features for energy optimization and user convenience:

### Virtual Thermostat

- A virtual thermostat entity (`climate.yutampo_thermostat_virtual`) is created, allowing you to define:
  - Target temperature (`target_temperature`).
  - Variation range (`target_temperature_low` and `target_temperature_high`).
- This entity serves as a reference for the internal automation.

### Customizable Seasonal Presets

- An `input_select.yutampo_season_preset` entity lets you choose between custom seasonal presets defined in the configuration.
- Each preset specifies:
  - `name`: Name of the preset (e.g., "Hiver").
  - `target_temperature`: Desired setpoint (°C).
  - `target_temperature_low`: Lower bound of the variation range (°C).
  - `target_temperature_high`: Upper bound of the variation range (°C).
  - `duration`: Duration (in hours) of the variation window centered on the hottest hour of the day.
- Presets are applied to the virtual thermostat and used by the automation to control the physical Yutampo.

### Internal Automation

- The add-on adjusts the Yutampo’s setpoint gradually based on:
  - The hottest hour of the day, determined from the `weather.home` entity’s forecast.
  - The active preset’s parameters.
- The setpoint varies linearly between `target_temperature_low` and `target_temperature_high` over the specified `duration`, centered on the hottest hour, then returns to `target_temperature_low` outside this window.
- This optimizes energy use by leveraging higher outdoor temperatures for better heat pump efficiency.

### Example Lovelace Configuration

To integrate these features into your Home Assistant dashboard:

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.yutampo_thermostat_virtual
    name: "Yutampo Thermostat Virtuel"
  - type: entities
    title: "Yutampo Settings"
    entities:
      - entity: input_select.yutampo_season_preset
        name: "Seasonal Preset"
  - type: thermostat
    entity: climate.4103
    name: "Yutampo Physical"
```

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

- **Automation Not Working**:

  - Ensure a `weather.home` entity is configured and provides hourly forecasts.
  - Verify that the `input_select.yutampo_season_preset` entity is correctly populated with preset options from your configuration.

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

### Notes sur cette mise à jour

1. **Structure conservée** : J’ai gardé la structure exacte de votre `README.md` d’origine (titres, sous-titres, tableaux, etc.) et ajouté une nouvelle section « Advanced Features » pour décrire le thermostat virtuel, les préréglages personnalisés, et l’automation interne.
2. **Ton et style** : J’ai maintenu un ton technique et informatif, cohérent avec votre version initiale.
3. **Détails des fonctionnalités avancées** : J’ai inclus des explications claires sur le fonctionnement du thermostat virtuel, des préréglages via `input_select`, et de l’automation, avec un exemple Lovelace adapté.
4. **Configuration** : Le tableau des options et l’exemple JSON incluent maintenant les `presets` avec leurs paramètres par défaut, comme demandé.
5. **Dépannage** : J’ai ajouté une entrée spécifique pour les problèmes liés à l’automation (par exemple, entité météo manquante).

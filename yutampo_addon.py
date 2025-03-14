import json
import os
import logging
import time
from api_client import ApiClient
from mqtt_handler import MqttHandler
from scheduler import Scheduler
from virtual_thermostat import VirtualThermostat
from weather_client import WeatherClient
from automation_handler import AutomationHandler


class YutampoAddon:
    def __init__(self, config_path):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.config = self._load_config(config_path)
        logging.getLogger().setLevel(getattr(logging, self.config["log_level"].upper()))
        self.logger.debug(f"Config initiale : {self.config}")
        self.api_client = ApiClient(self.config)
        self.mqtt_handler = MqttHandler(self.config, api_client=self.api_client)
        self.scheduler = Scheduler(self.api_client, self.mqtt_handler)
        self.devices = []
        self.virtual_thermostat = None
        self.weather_client = None
        self.automation_handler = None

    def _load_config(self, config_path):
        if not os.path.exists(config_path):
            self.logger.error(
                "Fichier de configuration introuvable ! Arrêt du programme."
            )
            exit(1)
        with open(config_path, "r") as config_file:
            config = json.load(config_file)

        mqtt_host = os.getenv("MQTTHOST") or os.getenv("MQTT_HOST")
        mqtt_port = os.getenv("MQTTPORT") or os.getenv("MQTT_PORT", "1883")
        mqtt_user = os.getenv("MQTTUSER") or os.getenv("MQTT_USERNAME")
        mqtt_password = os.getenv("MQTTPASSWORD") or os.getenv("MQTT_PASSWORD")
        ha_token = os.getenv("HASSIO_TOKEN")
        self.logger.debug(f"Token HA récupéré : {'présent' if ha_token else 'absent'}")

        scan_interval = config.get("scan_interval", 60)
        if not isinstance(scan_interval, (int, float)) or scan_interval < 60:
            self.logger.warning(
                f"scan_interval ({scan_interval}) doit être >= 60 secondes. Réglage à 60 secondes."
            )
            scan_interval = 60

        discovery_prefix = config.get("discovery_prefix", "homeassistant")
        weather_entity = config.get("weather_entity", "weather.forecast_maison")
        log_level = config.get("log_level", "DEBUG")

        presets = config.get(
            "presets",
            [
                {
                    "name": "Hiver",
                    "target_temperature": 50,
                    "target_temperature_low": 45,
                    "target_temperature_high": 55,
                    "duration": 6,
                },
                {
                    "name": "Printemps/Automne",
                    "target_temperature": 45,
                    "target_temperature_low": 41,
                    "target_temperature_high": 49,
                    "duration": 5,
                },
                {
                    "name": "Été",
                    "target_temperature": 40,
                    "target_temperature_low": 37,
                    "target_temperature_high": 43,
                    "duration": 4,
                },
            ],
        )

        for preset in presets:
            required_keys = [
                "name",
                "target_temperature",
                "target_temperature_low",
                "target_temperature_high",
                "duration",
            ]
            if not all(key in preset for key in required_keys):
                self.logger.error(
                    f"Préréglage mal formé : {preset}. Clés requises : {required_keys}"
                )
                exit(1)

        return {
            "username": config.get("username"),
            "password": config.get("password"),
            "scan_interval": scan_interval,
            "mqtt_host": mqtt_host,
            "mqtt_port": int(mqtt_port),
            "mqtt_user": mqtt_user,
            "mqtt_password": mqtt_password,
            "ha_token": ha_token,
            "presets": presets,
            "discovery_prefix": discovery_prefix,
            "weather_entity": weather_entity,
            "log_level": log_level,
        }

    def start(self):
        env_vars = {
            k: v if k != "MQTTPASSWORD" else "****" for k, v in os.environ.items()
        }
        self.logger.debug(f"Variables d'environnement : {env_vars}")

        if not all(
            [
                self.config["mqtt_host"],
                self.config["mqtt_port"],
                self.config["mqtt_user"],
                self.config["mqtt_password"],
            ]
        ):
            self.logger.error(
                "Les informations du broker MQTT sont incomplètes. Arrêt du programme."
            )
            exit(1)

        self.logger.info("Démarrage de l'addon...")
        self.mqtt_handler.connect()

        if not self.api_client.authenticate():
            self.logger.error("Impossible de s'authentifier. Arrêt de l'add-on.")
            exit(1)

        devices_data = self.api_client.get_devices()
        if not devices_data:
            self.logger.error(
                "Impossible de récupérer les données initiales des appareils."
            )
            exit(1)

        self.devices = devices_data
        for device in self.devices:
            device.register(self.mqtt_handler)

        self.scheduler.schedule_updates(self.devices, self.config["scan_interval"])

        self.virtual_thermostat = VirtualThermostat(self.mqtt_handler)
        self.mqtt_handler.register_virtual_thermostat(self.virtual_thermostat)

        self.mqtt_handler.register_settings_entities(self.config["presets"])

        self.weather_client = WeatherClient(self.config, self.automation_handler)
        self.weather_client.start()

        if self.devices:
            self.automation_handler = AutomationHandler(
                self.api_client,
                self.mqtt_handler,
                self.virtual_thermostat,
                self.devices[0],
                self.weather_client,
                self.config["presets"],
            )
            self.mqtt_handler.automation_handler = self.automation_handler
            self.automation_handler.start()

        self.logger.info(
            "Le planificateur et l'automation interne sont en cours d'exécution. Appuyez sur Ctrl+C pour arrêter."
        )
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
            self.automation_handler.scheduler.shutdown()
            self.weather_client.shutdown()
            self.mqtt_handler.disconnect()
            self.logger.info("Arrêt du programme.")


if __name__ == "__main__":
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()

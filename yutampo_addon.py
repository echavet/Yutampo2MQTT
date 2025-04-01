import json
import os
import logging
import time
from api_client import ApiClient
from mqtt_handler import MqttHandler
from scheduler import Scheduler
from weather_client import WeatherClient
from automation_handler import AutomationHandler

logging.VERBOSE = 5
logging.addLevelName(logging.VERBOSE, "VERBOSE")


def verbose(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.VERBOSE):
        self._log(logging.VERBOSE, message, args, **kwargs)


logging.Logger.verbose = verbose


class YutampoAddon:
    VALID_LOG_LEVELS = ["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR"]
    VALID_REGULATION_MODES = ["gradual", "step"]

    def __init__(self, config_path="/data/options.json"):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.config = self._load_config(config_path)
        log_level = self.config["log_level"].upper()
        if log_level not in self.VALID_LOG_LEVELS:
            self.logger.warning(
                f"Niveau de log invalide '{log_level}', utilisation de 'INFO'."
            )
            log_level = "INFO"
        logging.getLogger().setLevel(getattr(logging, log_level))
        self.logger.info(f"Log level configuré à : {log_level}")

        self.api_client = ApiClient(self.config)
        self.mqtt_handler = MqttHandler(self.config, api_client=self.api_client)
        self.scheduler = Scheduler(self.api_client, self.mqtt_handler)
        self.devices = []
        self.weather_client = WeatherClient(self.config)
        self.weather_client.mqtt_handler = self.mqtt_handler
        self.automation_handler = None

    def _load_config(self, config_path):
        if not os.path.exists(config_path):
            self.logger.error("Fichier de configuration introuvable ! Arrêt.")
            exit(1)
        with open(config_path, "r") as config_file:
            config = json.load(config_file)

        mqtt_host = (
            os.getenv("MQTTHOST") or os.getenv("MQTT_HOST") or config.get("mqtt_host")
        )
        mqtt_port = (
            os.getenv("MQTTPORT")
            or os.getenv("MQTT_PORT")
            or config.get("mqtt_port", "1883")
        )
        mqtt_user = (
            os.getenv("MQTTUSER")
            or os.getenv("MQTT_USERNAME")
            or config.get("mqtt_user")
        )
        mqtt_password = (
            os.getenv("MQTTPASSWORD")
            or os.getenv("MQTT_PASSWORD")
            or config.get("mqtt_password")
        )
        ha_token = os.getenv("HASSIO_TOKEN") or config.get("ha_token")
        scan_interval = config.get("scan_interval", 60)
        if not isinstance(scan_interval, (int, float)) or scan_interval < 60:
            self.logger.warning(
                f"scan_interval ({scan_interval}) doit être >= 60s. Réglé à 60s."
            )
            scan_interval = 60
        discovery_prefix = config.get("discovery_prefix") or "homeassistant"
        weather_entity = config.get("weather_entity")
        default_hottest_hour = config.get("default_hottest_hour", 15.0)
        setpoint = config.get("setpoint", 50.0)
        regulation_amplitude = config.get("regulation_amplitude")  # None si non défini
        heating_duration_hours = config.get("heating_duration_hours", 6.0)
        log_level = config.get("log_level", "INFO")

        regulation = config.get("regulation", "gradual").lower()  # Par défaut "gradual"
        if regulation not in self.VALID_REGULATION_MODES:
            self.logger.warning(
                f"Mode de régulation invalide '{regulation}', utilisation de 'gradual'."
            )
            regulation = "step"

        return {
            "username": config.get("username"),
            "password": config.get("password"),
            "scan_interval": scan_interval,
            "setpoint": setpoint,
            "regulation_amplitude": regulation_amplitude,
            "heating_duration_hours": heating_duration_hours,
            "mqtt_host": mqtt_host,
            "mqtt_port": int(mqtt_port),
            "mqtt_user": mqtt_user,
            "mqtt_password": mqtt_password,
            "ha_token": ha_token,
            "discovery_prefix": discovery_prefix,
            "weather_entity": weather_entity,
            "default_hottest_hour": default_hottest_hour,
            "log_level": log_level,
            "regulation": regulation,
        }

    def start(self):
        self.logger.info("Démarrage de l'addon...")

        if not self.api_client.authenticate():
            self.logger.error("Échec de l'authentification. Arrêt.")
            exit(1)

        devices_data = self.api_client.get_devices()
        if not devices_data:
            self.logger.error("Échec de la récupération des appareils.")
            exit(1)

        self.devices = devices_data

        self.mqtt_handler.connect()

        for device in self.devices:
            device.register(self.mqtt_handler)

        self.scheduler.schedule_updates(self.devices, self.config["scan_interval"])
        self.mqtt_handler.register_input_numbers()
        self.mqtt_handler.register_sensors()

        if self.devices:
            # Initialisation de l'amplitude : priorité aux options, sinon valeur par défaut
            initial_amplitude = self.config.get("regulation_amplitude")
            if initial_amplitude is not None:
                self.logger.info(
                    f"Amplitude de régulation thermique définie dans les options : {initial_amplitude}°C"
                )
            else:
                initial_amplitude = (
                    8  # Valeur par défaut si non défini dans les options
                )
                self.logger.info(
                    f"Amplitude de régulation thermique non définie dans les options, utilisation de la valeur par défaut : {initial_amplitude}°C"
                )

            initial_heating_duration = self.config.get("heating_duration_hours", 6.0)

            self.automation_handler = AutomationHandler(
                self.api_client,
                self.mqtt_handler,
                self.devices[0],
                self.weather_client,
                setpoint=self.config["setpoint"],
                amplitude=initial_amplitude,
                heating_duration=initial_heating_duration,
                regulation_mode=self.config["regulation"],
            )
            self.mqtt_handler.automation_handler = self.automation_handler
            self.weather_client.start()
            self.mqtt_handler.register_sensors()
            self.automation_handler.start()

            # Publier les états initiaux des capteurs
            self.logger.info(
                "Publication des états initiaux pour toutes les entités..."
            )
            self.mqtt_handler.publish_sensor_states(
                self.weather_client.get_hottest_hour(),
                self.weather_client.get_hottest_temperature(),
            )
            self.mqtt_handler.publish_input_number_state("yutampo_amplitude", 8)
            self.mqtt_handler.publish_input_number_state("yutampo_heating_duration", 6)
            self.mqtt_handler.publish_regulation_state(
                self.automation_handler.is_automatic()
            )

        self.logger.info("Addon démarré. Appuyez sur Ctrl+C pour arrêter.")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.shutdown()

    def shutdown(self):
        self.logger.info("Arrêt de l'addon...")
        # Mettre toutes les entités en indisponible
        for device in self.devices:
            device.set_unavailable(self.mqtt_handler)
        self.scheduler.shutdown()
        if self.automation_handler:
            self.automation_handler.scheduler.shutdown()
        self.weather_client.shutdown()
        self.mqtt_handler.disconnect()
        self.logger.info("Arrêt du programme.")


if __name__ == "__main__":
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()

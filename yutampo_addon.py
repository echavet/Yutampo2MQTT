# yutampo_addon.py
import json
import os
import logging
import time
from api_client import ApiClient
from mqtt_handler import MqttHandler
from scheduler import Scheduler


class YutampoAddon:
    def __init__(self, config_path):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.config = self._load_config(config_path)
        self.logger.debug(f"Config initiale : {self.config}")
        self.api_client = ApiClient(self.config)
        self.mqtt_handler = MqttHandler(self.config, api_client=self.api_client)
        self.scheduler = Scheduler(self.api_client, self.mqtt_handler)
        self.devices = []

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

        # Récupérer scan_interval et s'assurer qu'il est >= 60 secondes
        scan_interval = config.get("scan_interval", 60)
        if not isinstance(scan_interval, (int, float)) or scan_interval < 60:
            self.logger.warning(
                f"scan_interval ({scan_interval}) doit être >= 60 secondes. Réglage à 60 secondes."
            )
            scan_interval = 60

        return {
            "username": config.get("username"),
            "password": config.get("password"),
            "scan_interval": scan_interval,
            "mqtt_host": mqtt_host,
            "mqtt_port": int(mqtt_port),
            "mqtt_user": mqtt_user,
            "mqtt_password": mqtt_password,
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
        self.mqtt_handler.start()  # Démarrer la boucle MQTT et le heartbeat

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

        self.logger.info(
            "Le planificateur est en cours d'exécution. Appuyez sur Ctrl+C pour arrêter."
        )
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
            self.mqtt_handler.disconnect()
            self.logger.info("Arrêt du programme.")

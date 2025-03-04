# mqtt_handler.py
import paho.mqtt.client as mqtt
import json
import logging

class MqttHandler:
    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.mqtt_host = config["mqtt_host"]
        self.mqtt_port = config["mqtt_port"]
        self.mqtt_user = config["mqtt_user"]
        self.mqtt_password = config["mqtt_password"]

        # Logs pour déboguer
        self.logger.debug(f"Initialisation MqttHandler avec host={self.mqtt_host}, port={self.mqtt_port}, user={self.mqtt_user}")

        # Configuration des identifiants, mais pas de connexion immédiate
        self.client.username_pw_set(self.mqtt_user, self.mqtt_password)

    def connect(self):
        """Établit la connexion au broker MQTT"""
        if not self.mqtt_host:
            self.logger.error("MQTT host non défini. Impossible de se connecter.")
            raise ValueError("MQTT host cannot be empty or None")

        self.logger.info(f"Tentative de connexion au broker MQTT : {self.mqtt_host}:{self.mqtt_port}")
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.client.loop_start()
        except Exception as e:
            self.logger.error(f"Échec de la connexion au broker MQTT : {str(e)}")
            raise

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connecté au broker MQTT")
            self.client.subscribe("yutampo/climate/+/set")
        else:
            self.logger.error(f"Échec de la connexion au broker MQTT, code de retour : {rc}")

    def _on_message(self, client, userdata, msg):
        self.logger.info(f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}")
        try:
            device_id = msg.topic.split('/')[2]
            new_temp = float(msg.payload.decode())
            self.publish_state(device_id, temperature=new_temp, current_temperature=None)
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message: {str(e)}")

    def publish_discovery(self, device):
        discovery_topic = f"homeassistant/climate/{device.id}/config"
        payload = {
            "name": device.name,
            "unique_id": device.id,
            "modes": ["off", "heat"],
            "current_temperature_topic": f"yutampo/climate/{device.id}/current_temperature",
            "temperature_command_topic": f"yutampo/climate/{device.id}/set",
            "temperature_state_topic": f"yutampo/climate/{device.id}/temperature_state",
            "action_topic": f"yutampo/climate/{device.id}/action",
            "min_temp": 30,
            "max_temp": 60,
            "temp_step": 0.5,
            "availability_topic": f"yutampo/climate/{device.id}/availability",
            "device": {
                "identifiers": [device.id],
                "name": device.name,
                "manufacturer": "Yutampo",
                "model": "RS32"
            }
        }
        self.client.publish(discovery_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Configuration MQTT Discovery publiée pour l'appareil {device.name}")
        self.publish_availability(device.id, "online")

    def publish_state(self, device_id, temperature=None, current_temperature=None, mode=None, action=None):
        if temperature is not None:
            self.client.publish(f"yutampo/climate/{device_id}/temperature_state", temperature, retain=True)
        if current_temperature is not None:
            self.client.publish(f"yutampo/climate/{device_id}/current_temperature", current_temperature, retain=True)
        if mode is not None:
            self.client.publish(f"yutampo/climate/{device_id}/mode", mode, retain=True)
        if action is not None:
            self.client.publish(f"yutampo/climate/{device_id}/action", action, retain=True)
        self.logger.info(f"État publié pour {device_id}: consigne={temperature}, actuel={current_temperature}, mode={mode}, action={action}")

    def publish_availability(self, device_id, state):
        self.client.publish(f"yutampo/climate/{device_id}/availability", state, retain=True)
        self.logger.debug(f"Disponibilité publiée pour {device_id}: {state}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

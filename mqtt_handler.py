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
        self.client.username_pw_set(config["mqtt_user"], config["mqtt_password"])
        self.mqtt_host = config["mqtt_host"]
        self.mqtt_port = config["mqtt_port"]
        self.client.connect(self.mqtt_host, self.mqtt_port, 60)
        self.client.loop_start()

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
            "action_topic": f"yutampo/climate/{device.id}/action",  # Ajout de l'action_topic
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
        # Publier immédiatement l'état online
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
        """Publier l'état de disponibilité (online/offline)"""
        self.client.publish(f"yutampo/climate/{device_id}/availability", state, retain=True)
        self.logger.debug(f"Disponibilité publiée pour {device_id}: {state}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

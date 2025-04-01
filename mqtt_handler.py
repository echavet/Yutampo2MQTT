import paho.mqtt.client as mqtt
import json
import logging
import time


# Constantes pour les payloads des capteurs
DEVICE_INFO = {
    "identifiers": ["yutampo_settings"],
    "name": "Yutampo Settings",
    "manufacturer": "Yutampo",
    "model": "Settings",
}

HOTTEST_HOUR_PAYLOAD = {
    "name": "Yutampo Heure la Plus Chaude",
    "unique_id": "yutampo_hottest_hour",
    "state_topic": "yutampo/sensor/yutampo_hottest_hour/state",
    "unit_of_measurement": "h",
    "retain": True,
    "device": DEVICE_INFO,
    "device_class": "duration",
    "value_template": "{{ value | float | round(2) }}",
}

HOTTEST_TEMPERATURE_PAYLOAD = {
    "name": "Yutampo Température la Plus Chaude",
    "unique_id": "yutampo_hottest_temperature",
    "state_topic": "yutampo/sensor/yutampo_hottest_temperature/state",
    "unit_of_measurement": "°C",
    "retain": True,
    "device": DEVICE_INFO,
    "device_class": "temperature",
    "value_template": "{{ value | float }}",
}

REGULATION_STATE_PAYLOAD = {
    "name": "Yutampo État de Régulation",
    "unique_id": "yutampo_regulation_state",
    "state_topic": "yutampo/binary_sensor/yutampo_regulation_state/state",
    "device_class": "running",
    "payload_on": "true",
    "payload_off": "false",
    "retain": True,
    "device": DEVICE_INFO,
}

# Constantes pour les payloads des input_number (factorisation similaire)
AMPLITUDE_PAYLOAD = {
    "name": "Yutampo Amplitude Thermique",
    "unique_id": "yutampo_amplitude",
    "state_topic": "yutampo/input_number/yutampo_amplitude/state",
    "command_topic": "yutampo/input_number/yutampo_amplitude/set",
    "min": 0,
    "max": 20,
    "step": 1,
    "unit_of_measurement": "°C",
    "retain": True,
    "device": DEVICE_INFO,
    "mode": "box",
}

HEATING_DURATION_PAYLOAD = {
    "name": "Yutampo Heating Duration",
    "unique_id": "yutampo_heating_duration",
    "state_topic": "yutampo/input_number/yutampo_heating_duration/state",
    "command_topic": "yutampo/input_number/yutampo_heating_duration/set",
    "min": 1,
    "max": 24,
    "step": 0.5,
    "unit_of_measurement": "h",
    "retain": True,
    "device": DEVICE_INFO,
    "mode": "box",
}


class MqttHandler:
    def __init__(self, config, api_client=None):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.client = mqtt.Client(client_id="yutampo_addon", protocol=mqtt.MQTTv311)
        self.client.will_set(
            topic="yutampo/status", payload="offline", qos=1, retain=True
        )

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.mqtt_host = config["mqtt_host"]
        self.mqtt_port = config["mqtt_port"]
        self.mqtt_user = config["mqtt_user"]
        self.mqtt_password = config["mqtt_password"]
        self.discovery_prefix = config["discovery_prefix"]
        self.default_hottest_hour = config["default_hottest_hour"]
        self.api_client = api_client
        self.devices = {}
        self.automation_handler = None
        self.client.username_pw_set(self.mqtt_user, self.mqtt_password)

    def connect(self):
        if not self.mqtt_host:
            self.logger.error("MQTT host non défini. Impossible de se connecter.")
            raise ValueError("MQTT host cannot be empty or None")
        self.logger.info(
            f"Tentative de connexion au broker MQTT : {self.mqtt_host}:{self.mqtt_port}"
        )
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.client.loop_start()
        except Exception as e:
            self.logger.error(f"Échec de la connexion au broker MQTT : {str(e)}")
            raise

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connecté au broker MQTT")
            self.client.publish(
                topic="yutampo/status", payload="online", qos=1, retain=True
            )
            for device_id in self.devices:
                self.publish_availability(device_id, "online")

            self.subscribe_topics()
        else:
            self.logger.error(
                f"Échec de la connexion au broker MQTT, code de retour : {rc}"
            )

    def subscribe_topics(self):
        topics = [
            f"yutampo/climate/+/mode/set",
            f"yutampo/climate/+/set",
            f"yutampo/input_number/yutampo_amplitude/set",
            f"yutampo/input_number/yutampo_heating_duration/set",
        ]
        for topic in topics:
            self.client.subscribe(topic)
        self.logger.debug("Souscriptions aux topics MQTT effectuées.")

    def _on_message(self, client, userdata, msg):
        self.logger.info(
            f"Commande utilisateur reçue sur le topic {msg.topic}: {msg.payload.decode()}"
        )
        try:
            topic_parts = msg.topic.split("/")
            entity_type = topic_parts[1]
            device_id = topic_parts[2]
            command = topic_parts[3]
            payload = msg.payload.decode()

            if entity_type == "climate":
                if device_id not in self.devices:
                    self.logger.error(f"Device {device_id} inconnu.")
                    return
                device = self.devices[device_id]
                if command == "mode" and topic_parts[-1] == "set":
                    new_mode = payload
                    if new_mode not in ["off", "heat"]:
                        self.logger.warning(f"Mode non supporté : {new_mode}")
                        return
                    old_mode = device.mode
                    if self.automation_handler:
                        # Utiliser set_mode pour gérer le changement de mode
                        self.automation_handler.set_mode(new_mode)
                    else:
                        # Fallback si pas d'automation_handler
                        run_stop_dhw = 1 if new_mode == "heat" else 0
                        if self.api_client.set_heat_setting(
                            device.parent_id, run_stop_dhw=run_stop_dhw
                        ):
                            device.mode = new_mode
                            self.logger.info(
                                f"Changement de mode par l'utilisateur : {old_mode} -> {new_mode}"
                            )
                            self.publish_state(
                                device.id,
                                device.setting_temperature,
                                device.current_temperature,
                                device.mode,
                                device.action,
                                device.operation_label,
                                source="user",
                            )
                        else:
                            self.logger.error(
                                f"Échec de l'application du mode {new_mode}"
                            )
                elif command == "set":
                    new_temp = float(payload)
                    if not (30 <= new_temp <= 60):
                        self.logger.warning(
                            f"Température hors plage (30-60°C) : {new_temp}"
                        )
                        return
                    old_temp = device.setting_temperature
                    if self.automation_handler:
                        self.automation_handler.set_forced_setpoint(new_temp)
                    if self.api_client.set_heat_setting(
                        device.parent_id, setting_temp_dhw=new_temp
                    ):
                        device.setting_temperature = new_temp
                        self.logger.info(
                            f"Changement de consigne par l'utilisateur : {old_temp}°C -> {new_temp}°C"
                        )
                        self.publish_state(
                            device.id,
                            device.setting_temperature,
                            device.current_temperature,
                            device.mode,
                            device.action,
                            device.operation_label,
                            source="user",
                        )
                    else:
                        self.logger.error(
                            f"Échec de l'application de la température {new_temp}"
                        )

            elif entity_type == "input_number" and command == "set":
                if device_id == "yutampo_amplitude":
                    amplitude = float(payload)
                    if not (0 <= amplitude <= 20):
                        self.logger.warning(
                            f"Amplitude hors plage (0-20°C) : {amplitude}"
                        )
                        return
                    self.automation_handler.set_amplitude(amplitude)
                    self.publish_input_number_state(device_id, amplitude)
                    self.logger.info(
                        f"Changement d'amplitude par l'utilisateur : {amplitude}°C"
                    )
                elif device_id == "yutampo_heating_duration":
                    duration = float(payload)
                    if not (1 <= duration <= 24):
                        self.logger.warning(f"Durée hors plage (1-24h) : {duration}")
                        return
                    self.automation_handler.set_heating_duration(duration)
                    self.publish_input_number_state(device_id, duration)
                    self.logger.info(
                        f"Changement de durée de chauffe par l'utilisateur : {duration}h"
                    )
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message : {str(e)}")

    def _publish_discovery(
        self, entity_type, entity_id, payload, publish_state_func=None, state_args=None
    ):
        """Méthode générique pour publier un message MQTT Discovery."""
        topic = f"{self.discovery_prefix}/{entity_type}/{entity_id}/config"
        self.client.publish(topic, json.dumps(payload), retain=True)
        self.logger.info(f"Capteur MQTT Discovery publié pour {entity_id}")
        time.sleep(1)  # Délai pour garantir la découverte
        if publish_state_func and state_args:
            publish_state_func(*state_args)

    def publish_discovery(self, device):
        self.devices[device.id] = device
        discovery_topic = f"{self.discovery_prefix}/climate/{device.id}/config"
        payload = {
            "name": device.name,
            "unique_id": device.id,
            "modes": ["off", "heat"],
            "state_topic": f"yutampo/climate/{device.id}/state",
            "current_temperature_topic": f"yutampo/climate/{device.id}/current_temperature",
            "temperature_command_topic": f"yutampo/climate/{device.id}/set",
            "temperature_state_topic": f"yutampo/climate/{device.id}/temperature_state",
            "mode_state_topic": f"yutampo/climate/{device.id}/mode",
            "mode_command_topic": f"yutampo/climate/{device.id}/mode/set",
            "action_topic": f"yutampo/climate/{device.id}/hvac_action",
            "availability": [
                {"topic": f"yutampo/climate/{device.id}/availability"},
                {"topic": "yutampo/status"},
            ],
            "payload_available": "online",
            "payload_not_available": "offline",
            "min_temp": 30,
            "max_temp": 60,
            "temp_step": 1,
            "device": {
                "identifiers": [device.id],
                "name": device.name,
                "manufacturer": "Yutampo",
                "model": "RS32",
            },
        }
        self.client.publish(discovery_topic, json.dumps(payload), retain=True)
        self.logger.info(f"Configuration MQTT Discovery publiée pour {device.name}")
        self.publish_availability(device.id, "online")

    def publish_state(
        self,
        device_id,
        temperature=None,
        current_temperature=None,
        mode=None,
        action=None,
        operation_label=None,
        source="automation",
    ):
        if temperature is not None:
            self.client.publish(
                f"yutampo/climate/{device_id}/temperature_state",
                temperature,
                retain=True,
            )
        if current_temperature is not None:
            self.client.publish(
                f"yutampo/climate/{device_id}/current_temperature",
                current_temperature,
                retain=True,
            )
        if mode is not None:
            self.client.publish(f"yutampo/climate/{device_id}/mode", mode, retain=True)
        if action is not None:
            self.client.publish(
                f"yutampo/climate/{device_id}/hvac_action", action, retain=True
            )
        if operation_label is not None:
            self.client.publish(
                f"yutampo/climate/{device_id}/operation_label",
                operation_label,
                retain=True,
            )

        global_state = {
            "mode": mode if mode is not None else "",
            "temperature": float(temperature) if temperature is not None else 0,
            "current_temperature": (
                float(current_temperature) if current_temperature is not None else 0
            ),
            "action": action if action is not None else "",
            "operation_label": operation_label if operation_label is not None else "",
            "source": source,  # Nouvel attribut pour indiquer la source
        }
        self.client.publish(
            f"yutampo/climate/{device_id}/state", json.dumps(global_state), retain=True
        )
        self.logger.info(
            f"État publié pour {device_id} (source: {source}): {global_state}"
        )

    def publish_availability(self, device_id, state):
        self.client.publish(
            f"yutampo/climate/{device_id}/availability", state, retain=True
        )
        self.logger.debug(f"Disponibilité publiée pour {device_id}: {state}")

    def register_input_numbers(self):
        """Enregistre les input_number via MQTT Discovery."""
        # Amplitude thermique
        self._publish_discovery(
            entity_type="input_number",
            entity_id="yutampo_amplitude",
            payload=AMPLITUDE_PAYLOAD,
            publish_state_func=self.publish_input_number_state,
            state_args=("yutampo_amplitude", 8),
        )

        # Durée de chauffe
        self._publish_discovery(
            entity_type="input_number",
            entity_id="yutampo_heating_duration",
            payload=HEATING_DURATION_PAYLOAD,
            publish_state_func=self.publish_input_number_state,
            state_args=("yutampo_heating_duration", 6),
        )

        self.logger.info("Entités input_number publiées via MQTT Discovery.")

    def publish_input_number_state(self, entity_id, value):
        state_topic = f"yutampo/input_number/{entity_id}/state"
        self.client.publish(state_topic, str(value), retain=True)
        self.logger.info(f"État publié pour {entity_id}: {value}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def register_sensors(self):
        """Enregistre tous les capteurs via MQTT Discovery."""
        # Capteur pour l'heure la plus chaude
        self._publish_discovery(
            entity_type="sensor",
            entity_id="yutampo_hottest_hour",
            payload=HOTTEST_HOUR_PAYLOAD,
            publish_state_func=self.publish_sensor_states,
            state_args=(
                (
                    self.automation_handler.weather_client.get_hottest_hour()
                    if self.automation_handler
                    else 15.0
                ),
                None,
            ),
        )

        # Capteur pour la température la plus chaude
        self._publish_discovery(
            entity_type="sensor",
            entity_id="yutampo_hottest_temperature",
            payload=HOTTEST_TEMPERATURE_PAYLOAD,
            publish_state_func=self.publish_sensor_states,
            state_args=(
                None,
                (
                    self.automation_handler.weather_client.get_hottest_temperature()
                    if self.automation_handler
                    else None
                ),
            ),
        )

        # Capteur binaire pour l'état de la régulation
        self._publish_discovery(
            entity_type="binary_sensor",
            entity_id="yutampo_regulation_state",
            payload=REGULATION_STATE_PAYLOAD,
            publish_state_func=self.publish_regulation_state,
            state_args=(
                (
                    self.automation_handler.is_automatic()
                    if self.automation_handler
                    else True
                ),
            ),
        )

    def publish_regulation_state(self, is_automatic):
        """Publie l’état du capteur binaire yutampo_regulation_state."""
        self.client.publish(
            "yutampo/binary_sensor/yutampo_regulation_state/state",
            "true" if is_automatic else "false",
            retain=True,
        )
        self.logger.info(f"État de régulation publié : {is_automatic}")

    def publish_sensor_states(self, hottest_hour, hottest_temperature):
        if hottest_hour is not None:
            self.client.publish(
                "yutampo/sensor/yutampo_hottest_hour/state",
                str(round(hottest_hour, 2)) if hottest_hour is not None else "unknown",
                retain=True,
            )
        if hottest_temperature is not None:
            self.client.publish(
                "yutampo/sensor/yutampo_hottest_temperature/state",
                (
                    str(hottest_temperature)
                    if hottest_temperature is not None
                    else "unknown"
                ),
                retain=True,
            )
        self.logger.info(
            f"États des capteurs publiés : heure={hottest_hour}, temp={hottest_temperature}"
        )

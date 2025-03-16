# mqtt_handler.py
import paho.mqtt.client as mqtt
import json
import logging


class MqttHandler:

    def __init__(self, config, api_client=None):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        # Stocker les paramètres de configuration comme attributs
        self.mqtt_host = config["mqtt_host"]
        self.mqtt_port = config["mqtt_port"]
        self.mqtt_user = config["mqtt_user"]
        self.mqtt_password = config["mqtt_password"]

        # Initialiser le client MQTT avec un Client ID fixe
        self.client = mqtt.Client(client_id="yutampo-addon-4103")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = (
            self._on_disconnect
        )  # Ajouter gestion des déconnexions
        self.client.on_message = self._on_message
        self.client.username_pw_set(self.mqtt_user, self.mqtt_password)
        self.connected = False
        # Connecter dans __init__
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=15)
        self.client.loop_start()

    def connect(self):
        if not self.mqtt_host:
            self.logger.error("Hôte MQTT non défini !")
            return
        if not self.connected:
            self.logger.info("Tentative de connexion au broker MQTT...")
            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=15)
            self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connecté au broker MQTT avec succès")
            self.connected = True
            # S’abonner aux topics nécessaires
            self.client.subscribe("yutampo/climate/+/set")
            self.client.subscribe("yutampo/climate/+/mode/set")
        else:
            self.logger.error(f"Échec de la connexion au broker MQTT, code: {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        self.logger.warning(f"Déconnexion du broker MQTT, code: {rc}")
        self.connected = False
        if rc != 0:  # Déconnexion inattendue
            self.logger.info("Tentative de reconnexion au broker MQTT...")
            self.client.reconnect()

    def _on_message(self, client, userdata, msg):
        self.logger.info(
            f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}"
        )
        try:
            topic_parts = msg.topic.split("/")
            device_id = topic_parts[2]
            command_part = topic_parts[3]

            if device_id not in self.devices:
                self.logger.error(f"Device {device_id} inconnu dans DEVICES.")
                return

            device = self.devices[device_id]
            parent_id = device.parent_id
            current_mode = device.mode
            current_temp = device.setting_temperature

            payload = msg.payload.decode()

            if command_part == "mode" and topic_parts[-1] == "set":
                new_mode = payload
                if new_mode not in ["off", "heat"]:
                    self.logger.warning(f"Mode non supporté reçu : {new_mode}")
                    return
                run_stop_dhw = 1 if new_mode == "heat" else 0
                if self.api_client:
                    success = self.api_client.set_heat_setting(
                        parent_id, run_stop_dhw=run_stop_dhw
                    )
                    if success:
                        device.mode = new_mode
                        self.publish_state(
                            device.id,
                            device.setting_temperature,
                            device.current_temperature,
                            device.mode,
                            device.action,
                            device.operation_label,
                        )
                    else:
                        self.logger.error(
                            f"Échec de l'application du mode {new_mode} via API"
                        )
                else:
                    self.logger.warning(
                        "ApiClient non disponible, mode publié localement uniquement"
                    )
                    device.mode = new_mode
                    self.publish_state(
                        device.id,
                        device.setting_temperature,
                        device.current_temperature,
                        device.mode,
                        device.action,
                        device.operation_label,
                    )
            elif command_part == "set":
                new_temp = float(payload)
                if not (30 <= new_temp <= 60):
                    self.logger.warning(
                        f"Température hors plage (30-60°C) : {new_temp}"
                    )
                    return
                if self.api_client:
                    success = self.api_client.set_heat_setting(
                        parent_id, setting_temp_dhw=new_temp
                    )
                    if success:
                        device.setting_temperature = new_temp
                        self.publish_state(
                            device.id,
                            device.setting_temperature,
                            device.current_temperature,
                            device.mode,
                            device.action,
                            device.operation_label,
                        )
                    else:
                        self.logger.error(
                            f"Échec de l'application de la température {new_temp} via API"
                        )
                else:
                    self.logger.warning(
                        "ApiClient non disponible, température publiée localement uniquement"
                    )
                    device.setting_temperature = new_temp
                    self.publish_state(
                        device.id,
                        device.setting_temperature,
                        device.current_temperature,
                        device.mode,
                        device.action,
                        device.operation_label,
                    )
            else:
                self.logger.warning(
                    f"Type de commande inconnu reçu sur topic {msg.topic}: {payload}"
                )
        except ValueError as ve:
            self.logger.error(f"Erreur lors de la conversion de la valeur: {str(ve)}")
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message: {str(e)}")

    def publish_discovery(self, device):
        self.devices[device.id] = device
        discovery_topic = f"homeassistant/climate/{device.id}/config"
        payload = {
            "name": device.name,
            "unique_id": device.id,
            "modes": ["off", "heat"],
            "state_topic": f"yutampo/climate/{device.id}/state",  # Ajout pour logbook
            "current_temperature_topic": f"yutampo/climate/{device.id}/current_temperature",
            "temperature_command_topic": f"yutampo/climate/{device.id}/set",
            "temperature_state_topic": f"yutampo/climate/{device.id}/temperature_state",
            "mode_state_topic": f"yutampo/climate/{device.id}/mode",
            "mode_command_topic": f"yutampo/climate/{device.id}/mode/set",
            "action_topic": f"yutampo/climate/{device.id}/hvac_action",
            "availability_topic": f"yutampo/climate/{device.id}/availability",
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
        self.logger.info(
            f"Configuration MQTT Discovery publiée pour l'appareil {device.name}"
        )
        self.publish_availability(device.id, "online")

    def publish_state(
        self,
        device_id,
        temperature=None,
        current_temperature=None,
        mode=None,
        action=None,
        operation_label=None,
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

        # Publier un état global sur state_topic pour le logbook
        global_state = {
            "mode": mode if mode is not None else "",
            "temperature": temperature if temperature is not None else 0,
            "current_temperature": (
                current_temperature if current_temperature is not None else 0
            ),
            "action": action if action is not None else "",
            "operation_label": operation_label if operation_label is not None else "",
        }
        self.client.publish(
            f"yutampo/climate/{device_id}/state", json.dumps(global_state), retain=True
        )
        self.logger.info(
            f"État publié pour {device_id}: consigne={temperature}, actuel={current_temperature}, mode={mode}, action={action}, operation_label={operation_label}"
        )

    def publish_availability(self, device_id, state):
        if not self.connected:
            self.logger.warning("Client MQTT non connecté, tentative de reconnexion...")
            self.connect()
        self.client.publish(
            f"yutampo/climate/{device_id}/availability", state, retain=True
        )
        self.logger.debug(f"Disponibilité publiée pour {device_id}: {state}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Connexion MQTT arrêtée")

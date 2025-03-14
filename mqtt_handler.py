import paho.mqtt.client as mqtt
import json
import logging


class MqttHandler:
    def __init__(self, config, api_client=None):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.mqtt_host = config["mqtt_host"]
        self.mqtt_port = config["mqtt_port"]
        self.mqtt_user = config["mqtt_user"]
        self.mqtt_password = config["mqtt_password"]
        self.discovery_prefix = config["discovery_prefix"]
        self.api_client = api_client
        self.devices = {}
        self.virtual_thermostat = None
        self.automation_handler = None
        self.logger.debug(
            f"Initialisation MqttHandler avec host={self.mqtt_host}, port={self.mqtt_port}, user={self.mqtt_user}"
        )
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
        else:
            self.logger.error(
                f"Échec de la connexion au broker MQTT, code de retour : {rc}"
            )

    def subscribe_topics(self):
        topics = [
            f"yutampo/climate/{self.virtual_thermostat.device_id}/set_temperature",
            f"yutampo/climate/{self.virtual_thermostat.device_id}/set_temperature_low",
            f"yutampo/climate/{self.virtual_thermostat.device_id}/set_temperature_high",
            f"yutampo/climate/{self.virtual_thermostat.device_id}/set_mode",
            "yutampo/input_select/yutampo_season_preset/set",
        ]
        for topic in topics:
            self.client.subscribe(topic)
        self.logger.debug("Souscriptions aux topics MQTT effectuées.")

    def _on_message(self, client, userdata, msg):
        self.logger.info(
            f"Action utilisateur : Message reçu sur le topic {msg.topic}: {msg.payload.decode()}"
        )
        try:
            topic_parts = msg.topic.split("/")
            entity_type = topic_parts[1]
            device_id = topic_parts[2]
            command_part = topic_parts[3]
            payload = msg.payload.decode()

            if entity_type == "climate":
                if (
                    device_id not in self.devices
                    and device_id != "yutampo_thermostat_virtual"
                ):
                    self.logger.error(f"Device {device_id} inconnu dans DEVICES.")
                    return

                if device_id == "yutampo_thermostat_virtual":
                    if not self.virtual_thermostat:
                        self.logger.error(
                            "Thermostat virtuel non initialisé lors de la réception du message."
                        )
                        return
                    if command_part == "set_temperature":
                        new_temp = float(payload)
                        self.virtual_thermostat.set_temperature(new_temp)
                    elif command_part == "set_temperature_low":
                        new_temp_low = float(payload)
                        self.virtual_thermostat.set_temperature_low(new_temp_low)
                    elif command_part == "set_temperature_high":
                        new_temp_high = float(payload)
                        self.virtual_thermostat.set_temperature_high(new_temp_high)
                    elif command_part == "set_mode":
                        new_mode = payload
                        self.logger.debug(
                            f"Tentative de changement de mode vers : {new_mode}"
                        )
                        self.virtual_thermostat.set_mode(new_mode)
                    else:
                        self.logger.warning(
                            f"Commande inconnue pour thermostat virtuel : {command_part}"
                        )
                else:
                    device = self.devices[device_id]
                    parent_id = device.parent_id
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
            elif entity_type == "input_select" and command_part == "set":
                if device_id == "yutampo_season_preset" and self.automation_handler:
                    new_preset = payload
                    if new_preset in [
                        p["name"] for p in self.automation_handler.presets
                    ]:
                        self.automation_handler.set_season_preset(
                            new_preset
                        )  # Appel corrigé
                        self.publish_input_select_state(device_id, new_preset)
                    else:
                        self.logger.warning(f"Préréglage inconnu : {new_preset}")
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du message : {str(e)}")

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
        self.client.publish(
            f"yutampo/climate/{device_id}/availability", state, retain=True
        )
        self.logger.debug(f"Disponibilité publiée pour {device_id}: {state}")

    def register_virtual_thermostat(self, virtual_thermostat):
        self.virtual_thermostat = virtual_thermostat
        virtual_thermostat.register()
        self.subscribe_topics()

    def register_settings_entities(self, presets):
        input_select_topic = (
            f"{self.discovery_prefix}/input_select/yutampo_season_preset/config"
        )
        preset_names = [preset["name"] for preset in presets]
        self.logger.debug(f"Options publiées pour input_select : {preset_names}")
        input_select_payload = {
            "name": "Préréglage saisonnier du Yutampo",
            "unique_id": "yutampo_season_preset",
            "state_topic": "yutampo/input_select/yutampo_season_preset/state",
            "command_topic": "yutampo/input_select/yutampo_season_preset/set",
            "options": preset_names,
            "retain": True,
            "device": {
                "identifiers": ["yutampo_settings"],
                "name": "Yutampo Settings",
                "manufacturer": "Yutampo",
                "model": "Settings",
            },
        }
        self.logger.debug(
            f"Payload MQTT Discovery pour input_select : {json.dumps(input_select_payload)}"
        )
        self.client.publish(
            input_select_topic, json.dumps(input_select_payload), retain=True
        )
        self.logger.info(
            "Configuration MQTT Discovery publiée pour input_select.yutampo_season_preset"
        )
        self.publish_input_select_state("yutampo_season_preset", preset_names[0])

    def publish_input_select_state(self, entity_id, state):
        state_topic = f"yutampo/input_select/{entity_id}/state"
        self.client.publish(state_topic, state, retain=True)
        self.logger.info(
            f"État publié pour {entity_id}: {state}"
        )  # Plus précis que DEBUG

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

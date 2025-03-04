# mqtt_handler.py
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
        self.api_client = api_client  # Référence à ApiClient pour envoyer des commandes

        # Logs pour déboguer
        self.logger.debug(f"Initialisation MqttHandler avec host={self.mqtt_host}, port={self.mqtt_port}, user={self.mqtt_user}")

        # Configuration des identifiants
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
            # S'abonner aux topics de commande
            self.client.subscribe("yutampo/climate/+/set")  # Pour la température
            self.client.subscribe("yutampo/climate/+/mode/set")  # Pour le mode
        else:
            self.logger.error(f"Échec de la connexion au broker MQTT, code de retour : {rc}")

    def _on_message(self, client, userdata, msg):
        self.logger.info(f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}")
        try:
            topic_parts = msg.topic.split('/')
            device_id = topic_parts[2]  # Extrait l'ID du device
            command_part = topic_parts[3]  # "climate/{device_id}/[mode|set]"

            payload = msg.payload.decode()

            if command_part == "mode" and topic_parts[-1] == "set":  # Commande de mode (yutampo/climate/+/mode/set)
                new_mode = payload  # Pas de conversion en float, c'est une chaîne ("off", "heat")
                if new_mode in ["off", "heat"]:
                    # Convertir le mode en runStopDHW pour l'API
                    run_stop_dhw = 1 if new_mode == "heat" else 0
                    # Note : indoorId doit être obtenu, ici on suppose qu'il est connu
                    # Pour l'instant, on utilise un placeholder (4034 comme dans ton exemple)
                    # Cela devra être corrigé avec la bonne logique pour obtenir indoorId
                    indoor_id = "4034"  # TODO: Obtenir indoorId dynamiquement
                    if self.api_client:
                        success = self.api_client.set_heat_setting(indoor_id, run_stop_dhw)
                        if success:
                            self.publish_state(device_id, mode=new_mode)
                        else:
                            self.logger.error(f"Échec de l'application du mode {new_mode} via API")
                    else:
                        self.logger.warning("ApiClient non disponible, mode publié localement uniquement")
                        self.publish_state(device_id, mode=new_mode)
                else:
                    self.logger.warning(f"Mode non supporté reçu : {new_mode}")
            elif command_part == "set":  # Commande de température (yutampo/climate/+/set)
                new_temp = float(payload)  # Convertir en float pour les températures
                self.publish_state(device_id, temperature=new_temp, current_temperature=None)
                # Note : Si une API existe pour appliquer la température, on peut l'appeler ici
            else:
                self.logger.warning(f"Type de commande inconnu reçu sur topic {msg.topic}: {payload}")
        except ValueError as ve:
            self.logger.error(f"Erreur lors de la conversion de la valeur: {str(ve)}")
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
            "mode_state_topic": f"yutampo/climate/{device.id}/mode",
            "mode_command_topic": f"yutampo/climate/{device.id}/mode/set",
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

import json
import logging


class VirtualThermostat:
    def __init__(self, mqtt_handler, device_id="yutampo_thermostat_virtual"):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.mqtt_handler = mqtt_handler
        self.device_id = device_id
        self.target_temperature = 45.0
        self.target_temperature_low = 41.0
        self.target_temperature_high = 49.0
        self.mode = "heat"
        self.min_temp = 20  # Limite minimale globale
        self.max_temp = 60  # Limite maximale globale

    def register(self):
        discovery_topic = (
            f"{self.mqtt_handler.discovery_prefix}/climate/{self.device_id}/config"
        )
        payload = {
            "name": "Yutampo Thermostat Virtuel",
            "unique_id": self.device_id,
            "object_id": self.device_id,
            "temperature_command_topic": f"yutampo/climate/{self.device_id}/set_temperature",
            "temperature_state_topic": f"yutampo/climate/{self.device_id}/state",
            "temperature_state_template": "{{ value_json.temperature }}",
            "target_temperature_low_command_topic": f"yutampo/climate/{self.device_id}/set_temperature_low",
            "target_temperature_low_state_topic": f"yutampo/climate/{self.device_id}/state",
            "target_temperature_low_state_template": "{{ value_json.target_temperature_low }}",
            "target_temperature_high_command_topic": f"yutampo/climate/{self.device_id}/set_temperature_high",
            "target_temperature_high_state_topic": f"yutampo/climate/{self.device_id}/state",
            "target_temperature_high_state_template": "{{ value_json.target_temperature_high }}",
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "temp_step": 0.5,
            "modes": ["heat"],
            "mode_command_topic": f"yutampo/climate/{self.device_id}/set_mode",
            "mode_state_topic": f"yutampo/climate/{self.device_id}/state",
            "mode_state_template": "{{ value_json.mode }}",
            "availability_topic": f"yutampo/climate/{self.device_id}/availability",
            "retain": True,
            "device": {
                "identifiers": [self.device_id],
                "name": "Yutampo Thermostat Virtuel",
                "manufacturer": "Yutampo",
                "model": "Virtual",
            },
        }
        self.mqtt_handler.client.publish(
            discovery_topic, json.dumps(payload), retain=True
        )
        self.logger.info(
            f"Configuration MQTT Discovery publiée pour le thermostat virtuel {self.device_id}"
        )
        self.publish_availability("online")
        self.publish_state()

    def publish_state(self):
        state_topic = f"yutampo/climate/{self.device_id}/state"
        state_payload = {
            "temperature": self.target_temperature,
            "target_temperature_low": self.target_temperature_low,
            "target_temperature_high": self.target_temperature_high,
            "mode": self.mode,
        }
        self.mqtt_handler.client.publish(
            state_topic, json.dumps(state_payload), retain=True
        )
        self.logger.debug(f"État publié pour {self.device_id}: {state_payload}")

    def publish_availability(self, state):
        availability_topic = f"yutampo/climate/{self.device_id}/availability"
        self.mqtt_handler.client.publish(availability_topic, state, retain=True)
        self.logger.debug(f"Disponibilité publiée pour {self.device_id}: {state}")

    def set_temperature(self, temperature):
        if not (self.min_temp <= temperature <= self.max_temp):
            self.logger.warning(
                f"Température cible {temperature} hors plage [{self.min_temp}-{self.max_temp}]"
            )
            return
        self.target_temperature = temperature
        self.logger.info(f"Consigne cible mise à jour : {self.target_temperature}°C")
        # Recalculer les bornes en conservant l'amplitude existante si possible
        amplitude = (self.target_temperature_high - self.target_temperature_low) / 2
        self.target_temperature_low = max(self.min_temp, temperature - amplitude)
        self.target_temperature_high = min(self.max_temp, temperature + amplitude)
        self.log_weather_info()
        self.publish_state()

    def set_temperature_low(self, temperature_low):
        if not (self.min_temp <= temperature_low <= self.target_temperature):
            self.logger.warning(
                f"Température basse {temperature_low} hors plage [{self.min_temp}-{self.target_temperature}]"
            )
            return
        self.target_temperature_low = temperature_low
        self.logger.info(
            f"Température basse mise à jour : {self.target_temperature_low}°C"
        )
        self.log_weather_info()
        self.publish_state()

    def set_temperature_high(self, temperature_high):
        if not (self.target_temperature <= temperature_high <= self.max_temp):
            self.logger.warning(
                f"Température haute {temperature_high} hors plage [{self.target_temperature}-{self.max_temp}]"
            )
            return
        self.target_temperature_high = temperature_high
        self.logger.info(
            f"Température haute mise à jour : {self.target_temperature_high}°C"
        )
        self.log_weather_info()
        self.publish_state()

    def set_mode(self, mode):
        if mode in ["heat"]:
            self.mode = mode
            self.publish_state()
        else:
            self.logger.warning(f"Mode non supporté reçu : {mode}")

    def log_weather_info(self):
        """Ajoute des logs pour la météo et la plage active après un changement."""
        from automation_handler import (
            AutomationHandler,
        )  # Import local pour éviter une dépendance circulaire

        if (
            hasattr(self.mqtt_handler, "automation_handler")
            and self.mqtt_handler.automation_handler
        ):
            hottest_hour = (
                self.mqtt_handler.automation_handler.weather_client.get_hottest_hour()
            )
            duration = self.mqtt_handler.automation_handler.heating_duration
            start_hour = hottest_hour - (duration / 2)
            end_hour = hottest_hour + (duration / 2)
            if start_hour < 0:
                start_hour += 24
            if end_hour >= 24:
                end_hour -= 24
            self.logger.info(f"Heure la plus chaude : {hottest_hour:.2f}h")
            self.logger.info(
                f"Plage active du chauffage : {start_hour:.2f}h - {end_hour:.2f}h"
            )
            self.logger.info(
                f"Température par défaut en dehors de la plage : {self.target_temperature_low:.1f}°C"
            )

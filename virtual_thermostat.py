import json
import logging


class VirtualThermostat:
    def __init__(self, mqtt_handler, device_id="yutampo_thermostat_virtual"):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.mqtt_handler = mqtt_handler
        self.device_id = device_id
        self.target_temperature = 45.0  # Consigne cible initiale
        self.target_temperature_low = 41.0  # Point bas initial
        self.target_temperature_high = 49.0  # Point haut initial
        self.mode = "heat"  # Mode initial

    def register(self):
        """Publie la configuration MQTT Discovery pour le thermostat virtuel."""
        discovery_topic = f"homeassistant/climate/{self.device_id}/config"
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
            "min_temp": 20,
            "max_temp": 60,
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
        """Publie l'état actuel du thermostat virtuel."""
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
        """Publie la disponibilité du thermostat virtuel."""
        availability_topic = f"yutampo/climate/{self.device_id}/availability"
        self.mqtt_handler.client.publish(availability_topic, state, retain=True)
        self.logger.debug(f"Disponibilité publiée pour {self.device_id}: {state}")

    def set_temperature(self, temperature):
        """Met à jour la consigne cible et ajuste la plage de variation."""
        self.target_temperature = temperature
        amplitude = (self.target_temperature_high - self.target_temperature_low) / 2
        self.target_temperature_low = temperature - amplitude
        self.target_temperature_high = temperature + amplitude
        self.publish_state()

    def set_temperature_low(self, temperature_low):
        """Met à jour le point bas de la plage de variation."""
        self.target_temperature_low = temperature_low
        self.target_temperature = (
            self.target_temperature_low + self.target_temperature_high
        ) / 2
        self.publish_state()

    def set_temperature_high(self, temperature_high):
        """Met à jour le point haut de la plage de variation."""
        self.target_temperature_high = temperature_high
        self.target_temperature = (
            self.target_temperature_low + self.target_temperature_high
        ) / 2
        self.publish_state()

    def set_mode(self, mode):
        """Met à jour le mode du thermostat virtuel."""
        if mode in ["heat"]:
            self.mode = mode
            self.publish_state()
        else:
            self.logger.warning(f"Mode non supporté reçu : {mode}")

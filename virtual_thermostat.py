import json
import logging


class VirtualThermostat:
    def __init__(self, mqtt_handler, device_id="yutampo_thermostat_virtual"):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.mqtt_handler = mqtt_handler
        self.device_id = device_id
        self.target_temperature = 45.0
        self.target_temperature_low = 40.0
        self.target_temperature_high = 50.0
        self.mode = "heat"
        self.preset_mode = "Hiver"  # Préréglage initial

    def register(self):
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
            "preset_modes": ["Hiver", "Printemps/Automne", "Été"],
            "preset_mode_command_topic": f"yutampo/climate/{self.device_id}/set_preset_mode",
            "preset_mode_state_topic": f"yutampo/climate/{self.device_id}/state",
            "preset_mode_state_template": "{{ value_json.preset_mode }}",
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
            "preset_mode": self.preset_mode,
        }
        self.mqtt_handler.client.publish(
            state_topic, json.dumps(state_payload), retain=True
        )
        self.logger.debug(f"État publié pour {self.device_id}: {state_payload}")

    def set_preset_mode(self, preset_mode):
        if preset_mode in ["Hiver", "Printemps/Automne", "Été"]:
            self.preset_mode = preset_mode
            if preset_mode == "Hiver":
                self.set_temperature(50)
                self.set_temperature_low(45)
                self.set_temperature_high(55)
            elif preset_mode == "Printemps/Automne":
                self.set_temperature(45)
                self.set_temperature_low(41)
                self.set_temperature_high(49)
            elif preset_mode == "Été":
                self.set_temperature(40)
                self.set_temperature_low(37)
                self.set_temperature_high(43)
            self.publish_state()
        else:
            self.logger.warning(f"Préréglage non supporté reçu : {preset_mode}")

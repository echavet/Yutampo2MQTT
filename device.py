# device.py
import logging

class Device:
    def __init__(self, id, name):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.id = id
        self.name = name
        self.setting_temperature = None
        self.current_temperature = None
        self.mode = None
        self.action = None

    def register(self, mqtt_handler):
        mqtt_handler.publish_discovery(self)

    def update_state(self, mqtt_handler, state_data):
        """Met à jour l'état et publie via MQTT"""
        self.setting_temperature = state_data.get("settingTemperature", self.setting_temperature)
        self.current_temperature = state_data.get("currentTemperature", self.current_temperature)
        self.mode = "heat" if state_data.get("onOff") == 1 else "off"

        # Calcul de l'action basée sur les données
        if state_data.get("onOff") == 0:
            self.action = "off"
        elif state_data.get("doingBoost", False):
            self.action = "heating"
        elif state_data.get("operationStatus", 0) != 0:
            self.action = "heating"
        else:
            self.action = "idle"

        mqtt_handler.publish_state(self.id, self.setting_temperature, self.current_temperature, self.mode, self.action)

    def set_unavailable(self, mqtt_handler):
        """Marque l'appareil comme indisponible"""
        mqtt_handler.publish_availability(self.id, "offline")
        # On peut aussi publier une action "off" pour refléter l'état
        mqtt_handler.publish_state(self.id, action="off")

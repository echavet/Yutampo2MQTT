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

    def register(self, mqtt_handler):
        mqtt_handler.publish_discovery(self)

    def update_state(self, mqtt_handler, state_data):
        """Met à jour l'état et publie via MQTT"""
        self.setting_temperature = state_data.get("settingTemperature", self.setting_temperature)
        self.current_temperature = state_data.get("currentTemperature", self.current_temperature)
        self.mode = "heat" if state_data.get("onOff") == 1 else "off"
        mqtt_handler.publish_state(self.id, self.setting_temperature, self.current_temperature, self.mode)

    def set_unavailable(self, mqtt_handler):
        """Marque l'appareil comme indisponible"""
        mqtt_handler.publish_availability(self.id, "offline")

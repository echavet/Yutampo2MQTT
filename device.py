import logging


class Device:
    def __init__(self, id, name, parent_id):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.setting_temperature = None
        self.current_temperature = None
        self.mode = None
        self.action = None
        self.operation_status = None
        self.operation_label = None
        self.run_stop_dhw = None

    def register(self, mqtt_handler):
        mqtt_handler.publish_discovery(self)

    def update_state(self, mqtt_handler, state_data):
        self.setting_temperature = state_data.get(
            "settingTemperature", self.setting_temperature
        )
        self.current_temperature = state_data.get(
            "currentTemperature", self.current_temperature
        )
        self.operation_status = state_data.get("operationStatus", 0)
        self.run_stop_dhw = state_data.get("runStopDHW", "N/A")
        self.mode = "heat" if state_data.get("onOff") == 1 else "off"

        operation_status_map = {
            0: "idle",
            1: "idle",
            2: "off",
            3: "cooling",
            4: "idle",
            5: "off",
            6: "heating",
            7: "off",
            8: "heating",
            9: "off",
            10: "heating",
        }
        operation_label_map = {
            0: "Inactif",
            1: "Froid - Pas de demande",
            2: "Froid - Thermo OFF",
            3: "Froid - En demande",
            4: "Chaud - Pas de demande",
            5: "Chaud - Thermo OFF",
            6: "Chaud - En demande",
            7: "ECS Arrêt",
            8: "ECS Marche",
            9: "Piscine Arrêt",
            10: "Piscine Marche",
        }
        self.action = operation_status_map.get(self.operation_status, "idle")
        self.operation_label = operation_label_map.get(self.operation_status, "Inconnu")

        mqtt_handler.publish_state(
            self.id,
            self.setting_temperature,
            self.current_temperature,
            self.mode,
            self.action,
            self.operation_label,
        )

    def set_unavailable(self, mqtt_handler):
        mqtt_handler.publish_availability(self.id, "offline")
        mqtt_handler.publish_state(
            self.id,
            self.setting_temperature,
            self.current_temperature,
            self.mode,
            "off",
            self.operation_label,
        )

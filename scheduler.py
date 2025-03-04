# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
from device import Device

class Scheduler:
    def __init__(self, api_client, mqtt_handler):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.scheduler = BackgroundScheduler()
        self.devices = []

    def schedule_updates(self, devices, interval=300):
        self.devices = devices
        self.scheduler.add_job(
            self._update_data,
            trigger=IntervalTrigger(seconds=interval),
            next_run_time=datetime.now()
        )
        self.scheduler.start()

    def _update_data(self):
        self.logger.info("Mise à jour des données...")
        raw_data = self.api_client.get_raw_data()
        if not raw_data or "data" not in raw_data or "elements" not in raw_data["data"]:
            self.logger.warning("Échec de la récupération des données.")
            for device in self.devices:
                device.set_unavailable(self.mqtt_handler)
            return

        # Mettre à jour chaque appareil avec les nouvelles données
        device_map = {device.id: device for device in self.devices}
        for element in raw_data["data"]["elements"]:
            device_id = str(element["deviceId"])
            if device_id in device_map:
                device = device_map[device_id]
                device.update_state(self.mqtt_handler, element)
                self.mqtt_handler.publish_availability(device.id, "online")

    def shutdown(self):
        self.scheduler.shutdown()

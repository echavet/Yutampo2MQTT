from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import logging
import os
import sys


class Scheduler:
    def __init__(self, api_client, mqtt_handler):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.scheduler = BackgroundScheduler()
        self.devices = []
        self.failure_count = {}
        self.last_success_time = None
        self.base_interval = 60
        self.max_interval = 1200

    def schedule_updates(self, devices, interval=60):
        self.devices = devices
        self.base_interval = interval
        for device in self.devices:
            self.failure_count[device.id] = 0
        self.last_success_time = datetime.now()
        self._schedule_next_update()
        self.scheduler.start()

    def _schedule_next_update(self):
        max_failures = max(self.failure_count.values()) if self.failure_count else 0
        interval = self.base_interval * (2 ** min(max_failures, 4))
        interval = min(interval, self.max_interval)
        self.logger.debug(
            f"Planification prochaine mise à jour dans {interval} secondes (échecs max: {max_failures})"
        )

        self.scheduler.add_job(
            self._update_data,
            trigger=IntervalTrigger(seconds=interval),
            next_run_time=datetime.now() + timedelta(seconds=interval),
        )

    def _update_data(self):
        self.logger.info("Mise à jour des données...")
        raw_data = self.api_client.get_raw_data()
        if raw_data and "data" in raw_data and "elements" in raw_data["data"]:
            self.last_success_time = datetime.now()
            device_map = {device.id: device for device in self.devices}
            for element in raw_data["data"]["elements"]:
                device_id = str(element["deviceId"])
                if device_id in device_map:
                    device = device_map[device_id]
                    device.update_state(self.mqtt_handler, element)
                    self.mqtt_handler.publish_availability(device.id, "online")
                    self.failure_count[device.id] = 0
            self.logger.info("Mise à jour réussie.")
        else:
            self.logger.warning("Échec de la récupération des données.")
            for device in self.devices:
                self.failure_count[device.id] = min(
                    self.failure_count.get(device.id, 0) + 1, 3
                )
                if self.failure_count[device.id] >= 3:
                    device.set_unavailable(self.mqtt_handler)
                self.logger.info(
                    f"Échec pour {device.id}. Tentative {self.failure_count[device.id]}/3"
                )

            if self.last_success_time and (
                datetime.now() - self.last_success_time
            ) > timedelta(hours=1):
                self.logger.error(
                    "Échec persistant depuis plus d'une heure. Redémarrage de l'addon..."
                )
                self.shutdown()
                os.execv(sys.executable, [sys.executable] + sys.argv)

        self.scheduler.remove_all_jobs()
        self._schedule_next_update()

    def shutdown(self):
        self.scheduler.shutdown()

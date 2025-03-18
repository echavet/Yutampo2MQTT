from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import logging


class AutomationHandler:
    def __init__(
        self,
        api_client,
        mqtt_handler,
        physical_device,
        weather_client,
        setpoint,
        amplitude,
        heating_duration,
    ):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.physical_device = physical_device
        self.weather_client = weather_client
        self.scheduler = BackgroundScheduler()
        self.setpoint = setpoint  # Setpoint fixe depuis la config
        self.amplitude = amplitude  # Amplitude de variation thermique
        self.heating_duration = heating_duration  # Durée de chauffe en heures

    def start(self):
        self._schedule_automation()
        self.scheduler.start()
        self.logger.info("Automation interne démarrée.")

    def _schedule_automation(self):
        self.scheduler.add_job(
            self._run_automation,
            trigger=IntervalTrigger(minutes=5),
            next_run_time=datetime.now() + timedelta(seconds=5),
        )

    def set_amplitude(self, amplitude):
        self.amplitude = amplitude
        self.logger.info(f"Amplitude thermique mise à jour : {self.amplitude}°C")

    def set_heating_duration(self, duration):
        self.heating_duration = duration
        self.logger.info(f"Durée de chauffe mise à jour : {self.heating_duration}h")

    def _run_automation(self):
        self.logger.debug("Exécution de l'automation interne...")
        if self.amplitude <= 0:
            self.logger.debug("Amplitude thermique = 0, automation désactivée.")
            # Si l'appareil est en mode "heat", appliquer le setpoint fixe
            if self.physical_device.mode == "heat":
                target_temp = self.setpoint
                if self.api_client.set_heat_setting(
                    self.physical_device.parent_id,
                    run_stop_dhw=1,
                    setting_temp_dhw=target_temp,
                ):
                    self.physical_device.setting_temperature = target_temp
                    self.mqtt_handler.publish_state(
                        self.physical_device.id,
                        self.physical_device.setting_temperature,
                        self.physical_device.current_temperature,
                        self.physical_device.mode,
                        self.physical_device.action,
                        self.physical_device.operation_label,
                    )
                    self.logger.info(f"Consigne fixe appliquée : {target_temp}°C")
                else:
                    self.logger.error("Échec de l'application de la consigne fixe")
            return

        # Automation activée si amplitude > 0
        hottest_hour = (
            self.weather_client.get_hottest_hour()
            if self.weather_client
            else self.mqtt_handler.default_hottest_hour
        )
        start_hour = hottest_hour - (self.heating_duration / 2)
        end_hour = hottest_hour + (self.heating_duration / 2)

        current_time = datetime.now()
        current_hour = current_time.hour + current_time.minute / 60.0

        if start_hour < 0:
            start_hour += 24
        if end_hour >= 24:
            end_hour -= 24

        target_temp = self.setpoint  # Utilisation du setpoint configuré
        temp_min = target_temp - self.amplitude

        self.logger.info(f"Heure la plus chaude : {hottest_hour:.2f}h")
        self.logger.info(
            f"Plage active du chauffage : {start_hour:.2f}h - {end_hour:.2f}h"
        )
        self.logger.info(
            f"Température minimale : {temp_min:.1f}°C, consigne : {target_temp:.1f}°C"
        )

        if (current_hour >= start_hour and current_hour < end_hour) or (
            start_hour > end_hour
            and (current_hour >= start_hour or current_hour < end_hour)
        ):
            if current_hour >= start_hour:
                progress = (current_hour - start_hour) / self.heating_duration
            else:
                progress = (current_hour + 24 - start_hour) / self.heating_duration
            target_temp = temp_min + (target_temp - temp_min) * progress
        else:
            target_temp = temp_min

        target_temp = round(target_temp, 1)
        self.logger.debug(f"Consigne calculée : {target_temp}°C")

        if self.physical_device.mode == "heat":
            if self.api_client.set_heat_setting(
                self.physical_device.parent_id,
                run_stop_dhw=1,
                setting_temp_dhw=target_temp,
            ):
                self.physical_device.setting_temperature = target_temp
                self.mqtt_handler.publish_state(
                    self.physical_device.id,
                    self.physical_device.setting_temperature,
                    self.physical_device.current_temperature,
                    self.physical_device.mode,
                    self.physical_device.action,
                    self.physical_device.operation_label,
                )
                self.logger.info(f"Consigne appliquée : {target_temp}°C")
            else:
                self.logger.error("Échec de l'application de la consigne")

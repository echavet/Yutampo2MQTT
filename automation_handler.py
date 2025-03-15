import logging  # Ajouté ici
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import time  # Déjà ajouté précédemment


class AutomationHandler:
    def __init__(
        self,
        api_client,
        mqtt_handler,
        virtual_thermostat,
        physical_device,
        weather_client,
        presets,
    ):
        self.logger = logging.getLogger("Yutampo_ha_addon")  # Maintenant valide
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.virtual_thermostat = virtual_thermostat
        self.physical_device = physical_device
        self.weather_client = weather_client
        self.scheduler = BackgroundScheduler()
        self.presets = presets
        self.season_preset = self.presets[0]["name"]
        self.heating_duration = self.presets[0]["duration"]
        self.last_user_update = None  # Timestamp de la dernière mise à jour utilisateur

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

    def set_season_preset(self, preset_name):
        """Met à jour le preset saisonnier actif et synchronise le Climate Virtuel."""
        if preset_name not in [p["name"] for p in self.presets]:
            self.logger.warning(
                f"Preset {preset_name} non trouvé dans la liste des presets."
            )
            return
        self.season_preset = preset_name
        for preset in self.presets:
            if preset["name"] == preset_name:
                self.heating_duration = preset["duration"]
                self.logger.info(
                    f"Preset saisonnier mis à jour : {preset_name}, duration={self.heating_duration}"
                )
                # Synchroniser les paramètres du Climate Virtuel
                self.virtual_thermostat.sync_preset_parameters(
                    preset_name, self.presets
                )
                break

    def _run_automation(self):
        self.logger.debug("Exécution de l'automation interne...")
        if self.virtual_thermostat.mode != "auto":
            self.logger.debug(
                f"Mode {self.virtual_thermostat.mode} actif, optimisation désactivée."
            )
            return

        # Récupérer l'heure la plus chaude ou fallback sur le preset
        hottest_hour = (
            self.weather_client.get_hottest_hour()
            if self.weather_client
            else self.presets[0]["hottest_hour"]
        )
        start_hour = hottest_hour - (self.heating_duration / 2)
        end_hour = hottest_hour + (self.heating_duration / 2)

        current_time = datetime.now()
        current_hour = current_time.hour + current_time.minute / 60.0

        if start_hour < 0:
            start_hour += 24
        if end_hour >= 24:
            end_hour -= 24

        c = self.virtual_thermostat.target_temperature
        temp_min = self.virtual_thermostat.target_temperature_low
        temp_max = self.virtual_thermostat.target_temperature_high

        self.logger.info(f"Heure la plus chaude : {hottest_hour:.2f}h")
        self.logger.info(
            f"Plage active du chauffage : {start_hour:.2f}h - {end_hour:.2f}h"
        )
        self.logger.info(
            f"Température par défaut en dehors de la plage : {temp_min:.1f}°C"
        )

        # Respecter la consigne utilisateur pendant 5 minutes après un changement
        if self.last_user_update and (time.time() - self.last_user_update < 5 * 60):
            target_temp = c
            self.logger.info(
                f"Utilisation de la consigne utilisateur récente : {target_temp}°C (automation ignorée)"
            )
        else:
            # Calculer la consigne optimisée
            if (current_hour >= start_hour and current_hour < end_hour) or (
                start_hour > end_hour
                and (current_hour >= start_hour or current_hour < end_hour)
            ):
                if current_hour >= start_hour:
                    progress = (current_hour - start_hour) / self.heating_duration
                else:
                    progress = (current_hour + 24 - start_hour) / self.heating_duration
                if progress <= 0.5:
                    target_temp = temp_min + (c - temp_min) * (progress / 0.5)
                else:
                    target_temp = c + (temp_max - c) * ((progress - 0.5) / 0.5)
            else:
                target_temp = temp_min

            target_temp = round(target_temp, 1)
            self.logger.debug(f"Consigne calculée par optimisation : {target_temp}°C")

            # Appliquer au chauffe-eau physique
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
                self.logger.info(
                    f"Consigne optimisée appliquée au chauffe-eau physique : {target_temp}°C"
                )
            else:
                self.logger.error(
                    "Échec de l'application de la consigne optimisée au chauffe-eau physique"
                )

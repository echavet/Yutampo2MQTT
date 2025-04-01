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
        regulation_mode="step",
    ):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.physical_device = physical_device
        self.weather_client = weather_client
        self.scheduler = BackgroundScheduler()
        self.setpoint = setpoint
        self.amplitude = amplitude
        self.heating_duration = heating_duration
        self.regulation_mode = regulation_mode
        self.forced_setpoint = None
        self.locked_hottest_hour = None
        self.last_recalculation_date = None

    def start(self):
        self._recalculate_hottest_hour()  # Recalcul initial
        self._schedule_automation()
        self.scheduler.start()
        self.logger.info(
            f"Automation interne démarrée avec amplitude initiale : {self.amplitude if self.amplitude is not None else 'non définie (inactive)'}."
        )

    def _schedule_automation(self):
        self.scheduler.add_job(
            self._run_automation,
            trigger=IntervalTrigger(minutes=5),
            next_run_time=datetime.now() + timedelta(seconds=5),
        )
        self.scheduler.add_job(
            self._recalculate_hottest_hour,
            trigger="cron",
            hour=0,
            minute=0,
            next_run_time=datetime.now() if datetime.now().hour >= 0 else None,
        )

    def _recalculate_hottest_hour(self):
        current_date = datetime.now().date()
        if self.weather_client and self.last_recalculation_date != current_date:
            self.locked_hottest_hour = self.weather_client.get_hottest_hour()
            self.last_recalculation_date = current_date
            self.logger.info(
                f"Heure la plus chaude verrouillée pour aujourd'hui : {self.locked_hottest_hour:.2f}h"
            )
        elif not self.weather_client:
            self.locked_hottest_hour = self.mqtt_handler.default_hottest_hour
            self.last_recalculation_date = current_date

    def set_forced_setpoint(self, forced_setpoint):
        self.forced_setpoint = forced_setpoint
        self.logger.info(
            f"Demande forcée détectée : consigne définie à {self.forced_setpoint}°C, automation de régulation désactivée."
        )
        self._apply_forced_setpoint()
        self.mqtt_handler.publish_regulation_state(
            self.is_automatic()
        )  # Publier l’état

    def reset_forced_setpoint(self):
        self.forced_setpoint = None
        self.logger.info("Consigne forcée réinitialisée, automation normale reprise.")
        self.mqtt_handler.publish_regulation_state(
            self.is_automatic()
        )  # Publier l’état
        self._run_automation()

    def _apply_forced_setpoint(self):
        if self.physical_device.mode != "heat":
            self.logger.warning(
                f"Mode {self.physical_device.mode} actif, consigne forcée ignorée."
            )
            return

        if self.forced_setpoint is None:
            self.logger.warning("Aucune consigne forcée définie, rien à appliquer.")
            return

        success = self.api_client.set_heat_setting(
            self.physical_device.parent_id,
            run_stop_dhw=1,
            setting_temp_dhw=self.forced_setpoint,
        )
        if success:
            self.physical_device.setting_temperature = self.forced_setpoint
            self.mqtt_handler.publish_state(
                self.physical_device.id,
                self.physical_device.setting_temperature,
                self.physical_device.current_temperature,
                self.physical_device.mode,
                self.physical_device.action,
                self.physical_device.operation_label,
                source="user",
            )
            self.logger.info(f"Consigne forcée appliquée : {self.forced_setpoint}°C")
        else:
            self.logger.error("Échec de l'application de la consigne forcée")
            # Optionnel : réessayer ou signaler une erreur persistante

    def is_automatic(self):
        """Retourne True si la régulation automatique est active, False sinon."""
        return self.forced_setpoint is None

    def _run_automation(self):
        self.logger.debug("Exécution de l'automation interne...")

        if not self._can_run_automation():
            return

        if self._is_forced_setpoint_active():
            return

        self.logger.info("Automation normale en cours.")
        target_temp = self._calculate_target_temperature()
        self._apply_target_temperature(target_temp)

    def _can_run_automation(self):
        current_temp = self.physical_device.current_temperature
        if current_temp is None:
            self.logger.warning(
                "Température actuelle non disponible, attente de mise à jour."
            )
            return False  # Ne pas appeler _apply_forced_setpoint ici
        return True

    def _is_forced_setpoint_active(self):
        if self.forced_setpoint is None:
            return False

        current_temp = self.physical_device.current_temperature
        if current_temp is None:
            self.logger.warning(
                "Température actuelle non disponible, consigne forcée maintenue."
            )
            self._apply_forced_setpoint()
            return True

        if abs(current_temp - self.forced_setpoint) <= 1.0:
            self.logger.info(
                f"Consigne forcée {self.forced_setpoint}°C atteinte (actuel : {current_temp}°C), reprise de l'automation normale."
            )
            self.forced_setpoint = None
            self.mqtt_handler.publish_regulation_state(
                self.is_automatic()
            )  # Publier l’état
            return False
        else:
            self.logger.info(
                f"Consigne forcée {self.forced_setpoint}°C non atteinte (actuel : {current_temp}°C), automation reste désactivée."
            )
            self._apply_forced_setpoint()
            return True

    def _calculate_target_temperature(self):
        if self.amplitude is None or self.amplitude <= 0:
            self.logger.debug(
                "Amplitude thermique non définie ou nulle, régulation désactivée."
            )
            return self.setpoint

        # Utiliser l’heure verrouillée ou la valeur par défaut si non encore calculée
        hottest_hour = (
            self.locked_hottest_hour
            if self.locked_hottest_hour is not None
            else (
                self.weather_client.get_hottest_hour()
                if self.weather_client
                else self.mqtt_handler.default_hottest_hour
            )
        )
        start_hour, end_hour = self._get_heating_window(hottest_hour)
        current_hour = self._get_current_hour()

        self._log_heating_info(hottest_hour, start_hour, end_hour)

        if self._is_within_heating_window(current_hour, start_hour, end_hour):
            if self.regulation_mode == "step":
                # Mode "step" : consigne directement à setpoint
                self.logger.debug(
                    "Mode 'step' : consigne fixée directement à setpoint."
                )
                return self.setpoint
            else:
                # Mode "gradual" : calcul linéaire comme avant
                return self._compute_temperature_during_heating(
                    current_hour, start_hour, end_hour, hottest_hour
                )
        return self.setpoint - self.amplitude

    def _get_heating_window(self, hottest_hour):
        start_hour = hottest_hour - (self.heating_duration / 2)
        end_hour = hottest_hour + (self.heating_duration / 2)
        if start_hour < 0:
            start_hour += 24
        if end_hour >= 24:
            end_hour -= 24
        return start_hour, end_hour

    def _get_current_hour(self):
        current_time = datetime.now()
        return current_time.hour + current_time.minute / 60.0

    def _log_heating_info(self, hottest_hour, start_hour, end_hour):
        target_temp = self.setpoint
        temp_min = target_temp - self.amplitude
        self.logger.info(f"Heure la plus chaude : {hottest_hour:.2f}h")
        self.logger.info(
            f"Plage active du chauffage : {start_hour:.2f}h - {end_hour:.2f}h"
        )
        self.logger.info(
            f"Température minimale : {temp_min:.1f}°C, consigne de référence : {target_temp:.1f}°C"
        )

    def _is_within_heating_window(self, current_hour, start_hour, end_hour):
        return (current_hour >= start_hour and current_hour < end_hour) or (
            start_hour > end_hour
            and (current_hour >= start_hour or current_hour < end_hour)
        )

    def _compute_temperature_during_heating(
        self, current_hour, start_hour, end_hour, hottest_hour
    ):
        target_temp = self.setpoint
        temp_min = target_temp - self.amplitude
        half_duration = self.heating_duration / 2

        # Normalisation des heures pour éviter les problèmes de chevauchement sur minuit
        if start_hour > end_hour:  # Plage chevauchant minuit
            if current_hour < end_hour:
                current_hour += 24
            hottest_hour = (
                hottest_hour + 24 if hottest_hour < start_hour else hottest_hour
            )

        # Calcul linéaire de la progression
        if current_hour <= hottest_hour:
            # Montée vers la consigne maximale
            progress = (current_hour - start_hour) / half_duration
        else:
            # Descente vers la température minimale
            progress = (end_hour - current_hour) / half_duration

        # Assurer que progress reste entre 0 et 1
        progress = max(0, min(1, progress))
        target_temp = temp_min + (self.amplitude * progress)
        return round(target_temp, 1)

    def _apply_target_temperature(self, target_temp):
        self.logger.debug(f"Consigne calculée : {target_temp}°C")
        if self.physical_device.mode == "heat":
            self.mqtt_handler.publish_state(
                self.physical_device.id,
                target_temp,
                self.physical_device.current_temperature,
                self.physical_device.mode,
                self.physical_device.action,
                self.physical_device.operation_label,
                source="automation",
            )
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
                    source="automation",
                )
                self.logger.info(
                    f"Changement de consigne automatique : {target_temp}°C appliqué"
                )
            else:
                self.logger.error("Échec de l'application de la consigne")

    def set_mode(self, mode):  # Ajout pour gérer les changements de mode
        if mode == "off":
            self.api_client.set_heat_setting(
                self.physical_device.parent_id, run_stop_dhw=0, setting_temp_dhw=None
            )
            self.logger.info(f"Changement de mode par l'utilisateur : heat -> off")
        elif mode == "heat":
            self.api_client.set_heat_setting(
                self.physical_device.parent_id,
                run_stop_dhw=1,
                setting_temp_dhw=self.physical_device.setting_temperature,
            )
            self.logger.info(f"Changement de mode par l'utilisateur : off -> heat")
            self.reset_forced_setpoint()  # Forcer la reprise de la régulation
        self.mqtt_handler.publish_state(
            self.physical_device.id,
            self.physical_device.setting_temperature,
            self.physical_device.current_temperature,
            mode,
            self.physical_device.action,
            self.physical_device.operation_label,
            source="user",
        )

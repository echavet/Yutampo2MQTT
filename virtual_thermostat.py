import json
import logging
import time


class VirtualThermostat:
    def __init__(self, mqtt_handler, device_id="yutampo_thermostat_virtual"):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.mqtt_handler = mqtt_handler
        self.device_id = device_id
        self.target_temperature = 45.0
        self.target_temperature_low = 41.0
        self.target_temperature_high = 49.0
        self.mode = "auto"  # Mode par défaut changé à "auto"
        self.min_temp = 20
        self.max_temp = 60

    def register(self):
        discovery_topic = (
            f"{self.mqtt_handler.discovery_prefix}/climate/{self.device_id}/config"
        )
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
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "temp_step": 0.5,
            "modes": ["off", "heat", "auto"],  # Ajout des nouveaux modes
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
        availability_topic = f"yutampo/climate/{self.device_id}/availability"
        self.mqtt_handler.client.publish(availability_topic, state, retain=True)
        self.logger.debug(f"Disponibilité publiée pour {self.device_id}: {state}")

    def set_temperature(self, temperature):
        try:
            temp = float(temperature)
            self.logger.info(
                f"Action utilisateur : Nouvelle consigne définie à {temp}°C"
            )
            self.target_temperature = temp
            self._apply_to_physical_device()
            if (
                hasattr(self.mqtt_handler, "automation_handler")
                and self.mqtt_handler.automation_handler
            ):
                self.mqtt_handler.automation_handler.last_user_update = time.time()
            self.publish_state()
        except ValueError:
            self.logger.error(f"Consigne invalide reçue : {temperature}")

    def set_temperature_low(self, temperature_low):
        if not (self.min_temp <= temperature_low <= self.target_temperature):
            self.logger.warning(
                f"Température basse {temperature_low} hors plage [{self.min_temp}-{self.target_temperature}]"
            )
            return
        self.target_temperature_low = temperature_low
        self.logger.info(
            f"Action utilisateur : Température basse mise à jour à {self.target_temperature_low}°C"
        )
        self._log_weather_info()
        self._apply_mode_to_physical_device()
        self.publish_state()

    def set_temperature_high(self, temperature_high):
        if not (self.target_temperature <= temperature_high <= self.max_temp):
            self.logger.warning(
                f"Température haute {temperature_high} hors plage [{self.target_temperature}-{self.max_temp}]"
            )
            return
        self.target_temperature_high = temperature_high
        self.logger.info(
            f"Action utilisateur : Température haute mise à jour à {self.target_temperature_high}°C"
        )
        self._log_weather_info()
        self._apply_mode_to_physical_device()
        self.publish_state()

    def set_mode(self, mode):
        if mode not in ["off", "heat", "auto"]:
            self.logger.warning(f"Mode non supporté reçu : {mode}")
            return
        self.logger.info(f"Action utilisateur : Changement de mode vers {mode}")
        self.mode = mode
        self._apply_to_physical_device()
        if (
            hasattr(self.mqtt_handler, "automation_handler")
            and self.mqtt_handler.automation_handler
        ):
            self.mqtt_handler.automation_handler.last_user_update = time.time()
        self.publish_state()

    def _apply_to_physical_device(self):
        if (
            not hasattr(self.mqtt_handler, "automation_handler")
            or not self.mqtt_handler.automation_handler
        ):
            self.logger.debug(
                "AutomationHandler non disponible, pas d'application au chauffe-eau physique."
            )
            return
        physical_device = self.mqtt_handler.automation_handler.physical_device
        api_client = self.mqtt_handler.api_client

        if self.mode == "off":
            success = api_client.set_heat_setting(
                physical_device.parent_id, run_stop_dhw=0
            )
            if success:
                self.logger.info("Chauffe-eau physique arrêté (mode OFF)")
            else:
                self.logger.error("Échec de l'arrêt du chauffe-eau physique")
        elif self.mode == "heat":
            success = api_client.set_heat_setting(
                physical_device.parent_id,
                run_stop_dhw=1,
                setting_temp_dhw=self.target_temperature,
            )
            if success:
                self.logger.info(
                    f"Chauffe-eau physique en mode HEAT avec consigne {self.target_temperature}°C"
                )
            else:
                self.logger.error("Échec de la mise en marche du chauffe-eau physique")
        elif self.mode == "auto":
            success = api_client.set_heat_setting(
                physical_device.parent_id,
                run_stop_dhw=1,
                setting_temp_dhw=self.target_temperature,
            )
            if success:
                self.logger.info(
                    f"Chauffe-eau physique en mode AUTO avec consigne initiale {self.target_temperature}°C"
                )
            else:
                self.logger.error(
                    "Échec de la mise à jour du chauffe-eau physique en mode AUTO"
                )

        # Récupérer l’état immédiatement après la commande
        if success:
            self._update_physical_state(physical_device, api_client)

    def _update_physical_state(self, physical_device, api_client, max_retries=3):
        """Récupère et synchronise l'état réel du chauffe-eau physique immédiatement après une commande."""
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.logger.debug(
                f"Tentative {attempt}/{max_retries} de synchronisation de l'état du chauffe-eau physique."
            )
            try:
                raw_data = api_client.get_raw_data()
                if (
                    not raw_data
                    or "data" not in raw_data
                    or "elements" not in raw_data["data"]
                ):
                    self.logger.warning(
                        "Données brutes invalides ou manquantes lors de la synchronisation."
                    )
                    if attempt == max_retries:
                        self.logger.error(
                            "Échec de la synchronisation après toutes les tentatives."
                        )
                        return
                    time.sleep(2)  # Attendre 2 secondes avant de réessayer
                    continue

                for device in raw_data["data"]["elements"]:
                    if str(device["deviceId"]) == physical_device.id:
                        physical_device.current_temperature = device.get(
                            "currentTempDHW"
                        )
                        physical_device.setting_temperature = device.get(
                            "settingTempDHW"
                        )
                        physical_device.mode = (
                            "heat" if device.get("runStopDHW") == 1 else "off"
                        )
                        physical_device.action = (
                            "heating"
                            if device.get("operationStatus") in [6, 8, 10]
                            else "idle"
                        )
                        physical_device.operation_label = device.get(
                            "operationLabel", "unknown"
                        )
                        self.current_temperature = (
                            physical_device.current_temperature
                        )  # Synchroniser avec le virtuel

                        # Vérifier et synchroniser le mode du Climate Virtuel
                        expected_mode = (
                            "off" if physical_device.mode == "off" else self.mode
                        )
                        if self.mode != expected_mode:
                            self.logger.warning(
                                f"Incohérence du mode détectée : Climate Virtuel={self.mode}, Physique={physical_device.mode}. "
                                f"Synchronisation vers {expected_mode}."
                            )
                            self.mode = expected_mode
                            self.publish_state()

                        self.logger.info(
                            f"État synchronisé immédiatement : consigne={physical_device.setting_temperature}, "
                            f"actuel={physical_device.current_temperature}, mode={physical_device.mode}, "
                            f"action={physical_device.action}, operation_label={physical_device.operation_label}"
                        )
                        self.mqtt_handler.publish_state(
                            physical_device.id,
                            physical_device.setting_temperature,
                            physical_device.current_temperature,
                            physical_device.mode,
                            physical_device.action,
                            physical_device.operation_label,
                        )
                        return  # Succès, sortir de la boucle
            except Exception as e:
                self.logger.error(
                    f"Erreur lors de la synchronisation de l'état : {str(e)}"
                )
                if attempt == max_retries:
                    self.logger.error(
                        "Échec de la synchronisation après toutes les tentatives."
                    )
                    return
                time.sleep(2)  # Attendre 2 secondes avant de réessayer

    def _log_weather_info(self):
        if (
            hasattr(self.mqtt_handler, "automation_handler")
            and self.mqtt_handler.automation_handler
            and self.mqtt_handler.automation_handler.weather_client
        ):
            hottest_hour = (
                self.mqtt_handler.automation_handler.weather_client.get_hottest_hour()
            )
            duration = self.mqtt_handler.automation_handler.heating_duration
            start_hour = hottest_hour - (duration / 2)
            end_hour = hottest_hour + (duration / 2)
            if start_hour < 0:
                start_hour += 24
            if end_hour >= 24:
                end_hour -= 24
            self.logger.info(f"Heure la plus chaude : {hottest_hour:.2f}h")
            self.logger.info(
                f"Plage active du chauffage : {start_hour:.2f}h - {end_hour:.2f}h"
            )
            self.logger.info(
                f"Température par défaut en dehors de la plage : {self.target_temperature_low:.1f}°C"
            )

    def sync_preset_parameters(self, preset_name, presets):
        """Synchronise les paramètres du Climate Virtuel avec le preset actif."""
        for preset in presets:
            if preset["name"] == preset_name:
                self.target_temperature = preset["target_temperature"]
                self.target_temperature_low = preset["target_temperature_low"]
                self.target_temperature_high = preset["target_temperature_high"]
                self.logger.info(
                    f"Paramètres du Climate Virtuel synchronisés avec le preset {preset_name} : "
                    f"target_temperature={self.target_temperature}, "
                    f"target_temperature_low={self.target_temperature_low}, "
                    f"target_temperature_high={self.target_temperature_high}"
                )
                self.publish_state()
                return
        self.logger.warning(
            f"Preset {preset_name} non trouvé dans la liste des presets."
        )

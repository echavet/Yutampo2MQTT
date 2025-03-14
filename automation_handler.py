class AutomationHandler:
    def __init__(
        self,
        api_client,
        mqtt_handler,
        virtual_thermostat,
        physical_device,
        weather_client,
        preset_durations,
    ):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.api_client = api_client
        self.mqtt_handler = mqtt_handler
        self.virtual_thermostat = virtual_thermostat
        self.physical_device = physical_device
        self.weather_client = weather_client
        self.scheduler = BackgroundScheduler()
        self.preset_durations = preset_durations  # Durées associées aux préréglages
        self.season_preset = "Hiver"  # Préréglage par défaut
        self.heating_duration = self.preset_durations[
            self.season_preset
        ]  # Durée initiale

    def set_season_preset(self, preset):
        """Met à jour le préréglage saisonnier et ajuste la durée de variation."""
        if preset in self.preset_durations:
            self.season_preset = preset
            self.heating_duration = self.preset_durations[preset]
            self.logger.info(
                f"Préréglage saisonnier mis à jour : {self.season_preset}, durée de variation : {self.heating_duration} heures"
            )
        else:
            self.logger.warning(f"Préréglage inconnu : {preset}")

    def _apply_season_preset(self):
        """Supprimée car inutile avec la nouvelle logique."""
        pass

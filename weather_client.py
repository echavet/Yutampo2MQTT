import logging
import json
import aiohttp
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler


class WeatherClient:
    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.weather_entity = config["weather_entity"]
        self.ha_token = config["ha_token"]
        self.hottest_hour = 15  # Valeur par défaut
        self.scheduler = BackgroundScheduler()
        self.api_url = f"http://supervisor/core/api/states/{self.weather_entity}"

    def start(self):
        """Démarre le scheduler pour récupérer les prévisions périodiquement."""
        self.scheduler.add_job(
            self.fetch_forecast,
            trigger="interval",
            minutes=15,  # Mise à jour toutes les 15 minutes
            next_run_time=datetime.now(),
        )
        self.scheduler.start()
        self.logger.info(
            f"Démarrage de la récupération des prévisions pour {self.weather_entity} via API HA toutes les 15 minutes."
        )

    async def fetch_forecast(self):
        """Récupère les prévisions via l’API Home Assistant."""
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"Erreur lors de la récupération des prévisions : {response.status} - {await response.text()}"
                        )
                        return
                    weather_data = await response.json()
                    self.logger.debug(f"Données météo reçues via API : {weather_data}")
                    self._parse_forecast(weather_data)
        except Exception as e:
            self.logger.error(f"Erreur lors de la requête API HA : {str(e)}")

    def _parse_forecast(self, weather_data):
        """Parse les données de prévision pour trouver l’heure la plus chaude."""
        if (
            "attributes" not in weather_data
            or "forecast" not in weather_data["attributes"]
        ):
            self.logger.error(
                f"Aucune prévision trouvée dans les données de {self.weather_entity}"
            )
            return

        forecast = weather_data["attributes"]["forecast"]
        if not forecast:
            self.logger.error(f"Prévisions vides pour {self.weather_entity}")
            return

        hottest_temp = float("-inf")
        hottest_hour = 15

        for entry in forecast:
            temp = entry.get("temperature", float("-inf"))
            dt = datetime.strptime(entry["datetime"], "%Y-%m-%dT%H:%M:%S%z")
            hour = dt.hour + dt.minute / 60.0
            self.logger.debug(f"Prévision : {dt} -> {temp}°C")
            if temp > hottest_temp:
                hottest_temp = temp
                hottest_hour = hour

        self.hottest_hour = hottest_hour
        self.logger.info(
            f"Heure la plus chaude mise à jour via API HA : {self.hottest_hour:.2f}h avec {hottest_temp}°C"
        )

    def get_hottest_hour(self):
        return self.hottest_hour

    def shutdown(self):
        """Arrête le scheduler."""
        self.scheduler.shutdown()
        self.logger.info("Arrêt du scheduler de WeatherClient.")

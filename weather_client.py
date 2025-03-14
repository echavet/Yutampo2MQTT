import logging
from datetime import datetime


class WeatherClient:
    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.ha_token = config.get("ha_token")
        self.api_base_url = "http://supervisor/core/api"

    def get_hottest_hour(self):
        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json",
            }

            self.logger.debug(
                f"Tentative de récupération des données météo depuis {self.api_base_url}/states/weather.home"
            )
            response = requests.get(
                f"{self.api_base_url}/states/weather.home", headers=headers, timeout=10
            )
            self.logger.debug(
                f"Réponse HTTP : {response.status_code}, Contenu : {response.text}"
            )
            response.raise_for_status()
            weather_data = response.json()

            if (
                "attributes" not in weather_data
                or "forecast" not in weather_data["attributes"]
            ):
                self.logger.error(
                    "Aucune donnée de prévision disponible pour weather.home"
                )
                return 15

            forecast = weather_data["attributes"]["forecast"]
            if not forecast:
                self.logger.error("Prévisions vides pour weather.home")
                return 15

            hottest_temp = float("-inf")
            hottest_hour = 15

            for entry in forecast:
                temp = entry.get("temperature", float("-inf"))
                dt = datetime.strptime(entry["datetime"], "%Y-%m-%dT%H:%M:%S%z")
                hour = dt.hour + dt.minute / 60.0

                if temp > hottest_temp:
                    hottest_temp = temp
                    hottest_hour = hour

            self.logger.debug(
                f"Heure la plus chaude détectée : {hottest_hour}h avec {hottest_temp}°C"
            )
            return hottest_hour

        except Exception as e:
            self.logger.error(
                f"Erreur lors de la récupération des prévisions météo : {str(e)}"
            )
            return 15

import requests
import logging
from datetime import datetime


class WeatherClient:
    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.ha_api_url = "http://supervisor/core/api"  # URL de l'API HA via Supervisor
        self.ha_token = config.get("ha_token")  # Token d'accès à l'API HA
        self.weather_entity = "weather.home"  # Entité météo par défaut

    def get_hottest_hour(self):
        """Récupère l'heure la plus chaude de la journée à partir des prévisions météo."""
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }
        try:
            # Récupérer les attributs de l'entité météo
            response = requests.get(
                f"{self.ha_api_url}/states/{self.weather_entity}", headers=headers
            )
            if response.status_code == 200:
                weather_data = response.json()
                forecast = weather_data.get("attributes", {}).get("forecast", [])
                if not forecast:
                    self.logger.warning(
                        "Aucune prévision météo disponible. Utilisation de l'heure par défaut (15h)."
                    )
                    return 15

                # Trouver la température la plus élevée et son heure
                hottest = max(forecast, key=lambda x: x.get("temperature", 0))
                hottest_datetime = hottest.get("datetime")
                if hottest_datetime:
                    hottest_hour = datetime.strptime(
                        hottest_datetime, "%Y-%m-%dT%H:%M:%S%z"
                    ).hour
                    self.logger.debug(
                        f"Heure la plus chaude détectée : {hottest_hour}h"
                    )
                    return hottest_hour
                else:
                    self.logger.warning(
                        "Aucune donnée d'heure dans les prévisions. Utilisation de l'heure par défaut (15h)."
                    )
                    return 15
            else:
                self.logger.error(
                    f"Échec de la récupération des données météo. Code HTTP: {response.status_code}"
                )
                return 15
        except Exception as e:
            self.logger.error(
                f"Erreur lors de la récupération des données météo : {str(e)}"
            )
            return 15

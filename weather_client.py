import logging
import json
from datetime import datetime


class WeatherClient:
    def __init__(self, config, mqtt_handler):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.weather_entity = config["weather_entity"]
        self.mqtt_handler = mqtt_handler
        self.hottest_hour = 15  # Valeur par défaut
        self.mqtt_handler.client.on_message = self._on_message  # Surcharge du callback

    def subscribe(self):
        state_topic = f"{self.mqtt_handler.discovery_prefix}/weather/{self.weather_entity.split('.')[1]}/state"
        self.mqtt_handler.client.subscribe(state_topic)
        self.logger.info(f"Abonnement au topic météo : {state_topic}")

    def _on_message(self, client, userdata, msg):
        try:
            if (
                msg.topic
                == f"{self.mqtt_handler.discovery_prefix}/weather/{self.weather_entity.split('.')[1]}/state"
            ):
                weather_data = json.loads(msg.payload.decode())
                self.logger.debug(f"Données météo reçues : {weather_data}")
                if "forecast" not in weather_data:
                    self.logger.error(
                        f"Aucune prévision trouvée dans les données de {self.weather_entity}"
                    )
                    return

                forecast = weather_data["forecast"]
                if not forecast:
                    self.logger.error(f"Prévisions vides pour {self.weather_entity}")
                    return

                hottest_temp = float("-inf")
                hottest_hour = 15

                for entry in forecast:
                    temp = entry.get("temperature", float("-inf"))
                    dt = datetime.strptime(entry["datetime"], "%Y-%m-%dT%H:%M:%S%z")
                    hour = dt.hour + dt.minute / 60.0
                    if temp > hottest_temp:
                        hottest_temp = temp
                        hottest_hour = hour

                self.hottest_hour = hottest_hour
                self.logger.info(
                    f"Heure la plus chaude mise à jour via MQTT : {self.hottest_hour:.2f}h avec {hottest_temp}°C"
                )
        except Exception as e:
            self.logger.error(
                f"Erreur lors du traitement des données météo MQTT : {str(e)}"
            )

    def get_hottest_hour(self):
        return self.hottest_hour

import logging
import json
import websocket
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import time

logging.VERBOSE = 5
logging.addLevelName(logging.VERBOSE, "VERBOSE")


def verbose(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.VERBOSE):
        self._log(logging.VERBOSE, message, args, **kwargs)


logging.Logger.verbose = verbose


class WeatherClient:
    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.weather_entity = config.get("weather_entity")
        self.ha_token = config["ha_token"]
        self.default_hottest_hour = config["default_hottest_hour"]
        self.hottest_hour = self.default_hottest_hour
        self.scheduler = BackgroundScheduler()
        self.ws_url = "ws://supervisor/core/websocket"
        self.ws = None
        self.ws_thread = None
        self.message_id = 1
        self.connected = False
        self.hottest_temperature = None

    def start(self):
        if not self.weather_entity:
            self.logger.info(
                "Aucune entité météo spécifiée, utilisation de default_hottest_hour."
            )
            return
        self._connect_websocket()
        self.scheduler.add_job(
            self._request_forecast,
            trigger="interval",
            minutes=15,
            next_run_time=datetime.now(),
        )
        self.scheduler.start()
        self.logger.info(f"Prévisions météo démarrées pour {self.weather_entity}.")

    def _connect_websocket(self):
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                header={"Authorization": f"Bearer {self.ha_token}"},
            )
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            self.logger.info("Connexion WebSocket démarrée.")
            for _ in range(10):
                if self.connected:
                    break
                time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion WebSocket : {str(e)}")

    def _on_open(self, ws):
        self.connected = True
        self.logger.info("Connexion WebSocket ouverte.")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "auth_required":
                ws.send(json.dumps({"type": "auth", "access_token": self.ha_token}))
            elif data.get("type") == "auth_ok":
                self.logger.info("Authentification WebSocket réussie.")
                self._request_forecast()
            elif data.get("type") == "event" and "forecast" in data.get("event", {}):
                self._parse_forecast(data["event"]["forecast"])
        except Exception as e:
            self.logger.error(
                f"Erreur lors du traitement du message WebSocket : {str(e)}"
            )

    def _on_error(self, ws, error):
        self.connected = False
        self.logger.error(f"Erreur WebSocket : {str(error)}")
        self.hottest_hour = self.default_hottest_hour

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self.logger.info(
            f"Connexion WebSocket fermée : {close_status_code} - {close_msg}"
        )
        self.hottest_hour = self.default_hottest_hour

    def _request_forecast(self):
        if (
            not self.connected
            or not self.ws
            or not self.ws.sock
            or not self.ws.sock.connected
        ):
            self.logger.warning("WebSocket non connecté, tentative de reconnexion.")
            self._connect_websocket()
            return
        request = {
            "id": self.message_id,
            "type": "weather/subscribe_forecast",
            "entity_id": self.weather_entity,
            "forecast_type": "hourly",
        }
        self.ws.send(json.dumps(request))
        self.message_id += 1

    def _parse_forecast(self, forecast):
        if not forecast:
            self.logger.error("Prévisions vides, utilisation de default_hottest_hour.")
            self.hottest_hour = self.default_hottest_hour
            self.hottest_temperature = None
            return

        hottest_temp = float("-inf")
        hottest_hour = self.default_hottest_hour

        for entry in forecast:
            temp = entry.get("temperature", float("-inf"))
            dt = datetime.strptime(entry["datetime"], "%Y-%m-%dT%H:%M:%S%z")
            hour = dt.hour + dt.minute / 60.0
            if temp > hottest_temp:
                hottest_temp = temp
                hottest_hour = hour

        self.hottest_hour = hottest_hour
        self.hottest_temperature = (
            hottest_temp if hottest_temp != float("-inf") else None
        )

        self.logger.info(
            f"Heure la plus chaude : {self.hottest_hour:.2f}h, Température : {self.hottest_temperature}°C"
        )
        # Publier les nouveaux états via MQTT
        if hasattr(self, "mqtt_handler"):  # Vérifier si mqtt_handler est défini
            self.mqtt_handler.publish_sensor_states(
                self.hottest_hour, self.hottest_temperature
            )

    def get_hottest_hour(self):
        return self.hottest_hour

    def shutdown(self):
        self.scheduler.shutdown()
        if self.ws:
            self.ws.close()
        self.logger.info("WeatherClient arrêté.")

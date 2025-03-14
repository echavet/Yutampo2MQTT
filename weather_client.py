import logging
import json
import websocket
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import time


class WeatherClient:
    def __init__(self, config, automation_handler=None):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.weather_entity = config["weather_entity"]
        self.ha_token = config["ha_token"]
        self.automation_handler = automation_handler  # Pour récupérer le preset actif
        self.hottest_hour = (
            self._get_default_hottest_hour()
        )  # Valeur par défaut initiale
        self.scheduler = BackgroundScheduler()
        self.ws_url = "ws://supervisor/core/websocket"
        self.ws = None
        self.ws_thread = None
        self.message_id = 1
        self.connected = False

    def _get_default_hottest_hour(self):
        """Récupère l’heure la plus chaude par défaut depuis le preset actif."""
        if self.automation_handler and self.automation_handler.current_preset:
            preset = self.automation_handler.current_preset
            return preset.get("hottest_hour", 15)  # Fallback à 15h si non spécifié
        return 15

    def start(self):
        """Démarre le scheduler et la connexion WebSocket."""
        self._connect_websocket()
        self.scheduler.add_job(
            self._request_forecast,
            trigger="interval",
            minutes=15,
            next_run_time=datetime.now(),
        )
        self.scheduler.start()
        self.logger.info(
            f"Démarrage de la récupération des prévisions pour {self.weather_entity} via WebSocket HA toutes les 15 minutes."
        )

    def _connect_websocket(self):
        """Établit la connexion WebSocket."""
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
            # Attendre que la connexion soit établie
            for _ in range(10):  # 10 tentatives max (5 secondes)
                if self.connected:
                    break
                time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion WebSocket : {str(e)}")

    def _on_open(self, ws):
        """Appelé lorsque la connexion WebSocket est ouverte."""
        self.connected = True
        self.logger.info("Connexion WebSocket ouverte.")

    def _on_message(self, ws, message):
        """Traite les messages reçus via WebSocket."""
        try:
            data = json.loads(message)
            self.logger.debug(f"Message WebSocket reçu : {json.dumps(data, indent=2)}")
            if data.get("type") == "auth_required":
                ws.send(json.dumps({"type": "auth", "access_token": self.ha_token}))
                self.logger.debug("Envoi du token d’authentification.")
            elif data.get("type") == "auth_ok":
                self.logger.info("Authentification WebSocket réussie.")
                self._request_forecast()
            elif data.get("type") == "result" and "forecast" in data.get("result", {}):
                self._parse_forecast(data["result"]["forecast"])
        except Exception as e:
            self.logger.error(
                f"Erreur lors du traitement du message WebSocket : {str(e)}"
            )

    def _on_error(self, ws, error):
        """Log les erreurs WebSocket."""
        self.connected = False
        self.logger.error(f"Erreur WebSocket : {str(error)}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Log la fermeture de la connexion WebSocket."""
        self.connected = False
        self.logger.info(
            f"Connexion WebSocket fermée : {close_status_code} - {close_msg}"
        )

    def _request_forecast(self):
        """Demande les prévisions horaires via WebSocket."""
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
        self.logger.debug(f"Demande de prévisions envoyée : {json.dumps(request)}")
        self.message_id += 1

    def _parse_forecast(self, forecast):
        """Parse les données de prévision pour trouver l’heure la plus chaude."""
        if not forecast:
            self.logger.error(
                f"Prévisions vides pour {self.weather_entity}. Utilisation de l’heure par défaut."
            )
            self.hottest_hour = self._get_default_hottest_hour()
            return

        hottest_temp = float("-inf")
        hottest_hour = self._get_default_hottest_hour()

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
            f"Heure la plus chaude mise à jour via WebSocket HA : {self.hottest_hour:.2f}h avec {hottest_temp}°C"
        )

    def get_hottest_hour(self):
        return self.hottest_hour

    def shutdown(self):
        """Arrête le scheduler et ferme la connexion WebSocket."""
        self.scheduler.shutdown()
        if self.ws:
            self.ws.close()
        self.logger.info(
            "Arrêt du scheduler et de la connexion WebSocket de WeatherClient."
        )

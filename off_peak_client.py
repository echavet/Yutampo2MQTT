# off_peak_client.py — Écoute l'état d'un binary_sensor HC/HP via WebSocket HA
# Dépendances : websocket-client, json, threading

import logging
import json
import websocket
import threading
import time


class OffPeakClient:
    """Client WebSocket pour suivre l'état HC/HP d'un binary_sensor HA.

    - is_off_peak() retourne True en heures creuses (binary_sensor = on).
    - Fallback conservateur : False (HP) si déconnecté ou erreur.
    - Reconnexion automatique avec backoff exponentiel.
    """

    MAX_RECONNECT_DELAY = 300  # 5 minutes max

    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.entity_id = config.get("off_peak_entity")
        self.ha_token = config["ha_token"]
        self.ws_url = "ws://supervisor/core/websocket"
        self.ws = None
        self.ws_thread = None
        self.message_id = 1
        self.connected = False
        self._is_off_peak = False
        self._state_received = False
        self._shutdown_requested = False
        self._reconnect_delay = 5
        self.mqtt_handler = None

    def start(self):
        """Démarre la connexion WebSocket et souscrit aux changements d'état."""
        if not self.entity_id:
            self.logger.info(
                "Aucune entité HC/HP configurée, OffPeakClient inactif."
            )
            return
        self._connect_websocket()
        self.logger.info(
            f"OffPeakClient démarré, surveillance de {self.entity_id}."
        )

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
            self.logger.info("OffPeakClient : connexion WebSocket démarrée.")
            for _ in range(10):
                if self.connected:
                    break
                time.sleep(0.5)
        except Exception as e:
            self.logger.error(
                f"OffPeakClient : erreur connexion WebSocket : {str(e)}"
            )

    def _on_open(self, ws):
        self.connected = True
        self.message_id = 1
        self._reconnect_delay = 5  # Reset backoff
        self.logger.info("OffPeakClient : connexion WebSocket ouverte.")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "auth_required":
                ws.send(json.dumps({
                    "type": "auth",
                    "access_token": self.ha_token,
                }))

            elif msg_type == "auth_ok":
                self.logger.info("OffPeakClient : authentification réussie.")
                self._request_initial_state()
                self._subscribe_state_changes()

            elif msg_type == "result" and data.get("success"):
                # Réponse à get_states : extraction de l'état initial
                result = data.get("result")
                if isinstance(result, list):
                    for entity in result:
                        if entity.get("entity_id") == self.entity_id:
                            self._update_state(entity.get("state"))
                            break

            elif msg_type == "event":
                event_data = data.get("event", {}).get("data", {})
                entity_id = event_data.get("entity_id")
                if entity_id == self.entity_id:
                    new_state = event_data.get("new_state", {}).get("state")
                    self._update_state(new_state)

        except Exception as e:
            self.logger.error(
                f"OffPeakClient : erreur traitement message : {str(e)}"
            )

    def _on_error(self, ws, error):
        self.connected = False
        self._is_off_peak = False  # Fallback conservateur → HP
        self.logger.error(f"OffPeakClient : erreur WebSocket : {str(error)}")
        self._reconnect()

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self._is_off_peak = False  # Fallback conservateur → HP
        self.logger.info(
            f"OffPeakClient : WebSocket fermée : {close_status_code} - {close_msg}"
        )
        self._reconnect()

    def _reconnect(self):
        """Reconnexion avec backoff exponentiel (5s, 10s, 20s... max 300s)."""
        if self._shutdown_requested:
            return
        delay = self._reconnect_delay
        self._reconnect_delay = min(delay * 2, self.MAX_RECONNECT_DELAY)
        self.logger.info(
            f"OffPeakClient : reconnexion dans {delay}s..."
        )

        def _do_reconnect():
            time.sleep(delay)
            if not self._shutdown_requested:
                self._connect_websocket()

        t = threading.Thread(target=_do_reconnect)
        t.daemon = True
        t.start()

    def _request_initial_state(self):
        """Récupère l'état initial via get_states."""
        request = {
            "id": self.message_id,
            "type": "get_states",
        }
        self.ws.send(json.dumps(request))
        self.message_id += 1

    def _subscribe_state_changes(self):
        """Souscrit aux changements d'état via state_changed."""
        request = {
            "id": self.message_id,
            "type": "subscribe_events",
            "event_type": "state_changed",
        }
        self.ws.send(json.dumps(request))
        self.message_id += 1

    def _update_state(self, state):
        """Met à jour l'état HC/HP et publie sur MQTT si disponible."""
        previous = self._is_off_peak
        self._is_off_peak = (state == "on")
        self._state_received = True

        label = "HC (off-peak)" if self._is_off_peak else "HP (peak)"
        self.logger.info(f"OffPeakClient : état mis à jour → {label}")

        if self._is_off_peak != previous and self.mqtt_handler:
            self.mqtt_handler.publish_off_peak_state(self._is_off_peak)

    def is_off_peak(self):
        """Retourne True si HC, False si HP. Fallback : False (conservateur)."""
        return self._is_off_peak

    def shutdown(self):
        self._shutdown_requested = True
        if self.ws:
            self.ws.close()
        self.logger.info("OffPeakClient arrêté.")

# off_peak_client.py — Écoute l'état d'un binary_sensor HC/HP via WebSocket HA
# Dépendances : websocket-client, json, threading, requests

import logging
import json
import websocket
import threading
import time
import requests


class OffPeakClient:
    """Client WebSocket pour suivre l'état HC/HP d'un binary_sensor HA.

    - is_off_peak() retourne True en heures creuses (binary_sensor = on).
    - Fallback conservateur : False (HP) si déconnecté ou erreur.
    - Reconnexion automatique robuste avec backoff exponentiel (max 60s).
    - Watchdog : si aucune activité (message ou pong) pendant watchdog_timeout, force reconnexion.
    - Fallback REST : récupère périodiquement l'état via /api/states/<entity>.
    """

    MAX_RECONNECT_DELAY = 60  # 60 seconds max (was 300s, now more aggressive)
    INITIAL_RECONNECT_DELAY = 5
    WATCHDOG_TIMEOUT = 120  # 2 minutes without any activity triggers reconnect
    REST_FALLBACK_INTERVAL = 60  # Check state via REST every 60s when disconnected

    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.entity_id = config.get("off_peak_entity")
        self.ha_token = config["ha_token"]
        self.ws_url = "ws://supervisor/core/websocket"
        self.rest_url = "http://supervisor/core/api"
        self.ws = None
        self.ws_thread = None
        self.message_id = 1
        self.connected = False
        self._is_off_peak = False
        self._state_received = False
        self._shutdown_requested = False
        self._reconnect_delay = self.INITIAL_RECONNECT_DELAY
        self._lock = threading.Lock()
        self._reconnect_scheduled = False
        self._connecting = False  # Prevents concurrent connection attempts
        self._last_activity_time = 0  # Updated by messages AND pongs
        self._watchdog_thread = None
        self._rest_fallback_thread = None
        self.mqtt_handler = None

    def start(self):
        """Démarre la connexion WebSocket et souscrit aux changements d'état."""
        if not self.entity_id:
            self.logger.info(
                "Aucune entité HC/HP configurée, OffPeakClient inactif."
            )
            return
        self._shutdown_requested = False
        self._last_activity_time = time.time()
        self._start_watchdog()
        self._start_rest_fallback()
        self._connect_websocket()
        self.logger.info(
            f"OffPeakClient démarré, surveillance de {self.entity_id}."
        )

    def _start_watchdog(self):
        """Démarre le thread watchdog qui surveille la santé de la connexion."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return

        def watchdog_loop():
            while not self._shutdown_requested:
                time.sleep(30)  # Check every 30 seconds
                if self._shutdown_requested:
                    break
                elapsed = time.time() - self._last_activity_time
                if self.connected and elapsed > self.WATCHDOG_TIMEOUT:
                    self.logger.warning(
                        f"OffPeakClient watchdog : aucune activité depuis {elapsed:.0f}s, "
                        "forçage de la reconnexion."
                    )
                    self._force_reconnect()
                elif not self.connected:
                    # If not connected and no reconnect scheduled, schedule one
                    with self._lock:
                        if not self._reconnect_scheduled and not self._connecting and not self._shutdown_requested:
                            self.logger.warning(
                                "OffPeakClient watchdog : connexion perdue, planification reconnexion."
                            )
                            self._schedule_reconnect()

        self._watchdog_thread = threading.Thread(target=watchdog_loop, name="OffPeakWatchdog")
        self._watchdog_thread.daemon = True
        self._watchdog_thread.start()
        self.logger.debug("OffPeakClient : watchdog démarré.")

    def _start_rest_fallback(self):
        """Démarre le thread de fallback REST pour récupérer l'état périodiquement."""
        if self._rest_fallback_thread and self._rest_fallback_thread.is_alive():
            return

        def rest_fallback_loop():
            while not self._shutdown_requested:
                time.sleep(self.REST_FALLBACK_INTERVAL)
                if self._shutdown_requested:
                    break
                # Use REST fallback when disconnected OR as periodic verification
                if not self.connected or not self._state_received:
                    self._fetch_state_via_rest()

        self._rest_fallback_thread = threading.Thread(target=rest_fallback_loop, name="OffPeakREST")
        self._rest_fallback_thread.daemon = True
        self._rest_fallback_thread.start()
        self.logger.debug("OffPeakClient : fallback REST démarré.")

    def _fetch_state_via_rest(self):
        """Récupère l'état de l'entité via l'API REST de HA."""
        try:
            url = f"{self.rest_url}/states/{self.entity_id}"
            headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json",
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                state = data.get("state")
                self.logger.info(
                    f"OffPeakClient REST fallback : état récupéré → {state}"
                )
                self._update_state(state, source="REST")
            else:
                self.logger.warning(
                    f"OffPeakClient REST fallback : erreur HTTP {response.status_code}"
                )
        except requests.exceptions.Timeout:
            self.logger.warning("OffPeakClient REST fallback : timeout")
        except Exception as e:
            self.logger.warning(
                f"OffPeakClient REST fallback : erreur {str(e)}"
            )

    def _connect_websocket(self):
        """Établit la connexion WebSocket (thread-safe, prevents concurrent attempts)."""
        with self._lock:
            if self._connecting or self._shutdown_requested:
                return
            self._connecting = True

        try:
            # Clean up previous connection
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    self.logger.debug(f"OffPeakClient : erreur fermeture ancien WS : {str(e)}")
                self.ws = None
            if self.ws_thread and self.ws_thread.is_alive():
                self.ws_thread.join(timeout=2.0)
                self.ws_thread = None

            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_ping=self._on_ping,
                on_pong=self._on_pong,
                header={"Authorization": f"Bearer {self.ha_token}"},
            )
            self.ws_thread = threading.Thread(target=self._run_ws_forever, name="OffPeakWS")
            self.ws_thread.daemon = True
            self.ws_thread.start()
            self.logger.info("OffPeakClient : connexion WebSocket démarrée.")

            # Wait for connection with timeout
            connect_timeout = 10
            for _ in range(connect_timeout * 2):
                if self.connected or self._shutdown_requested:
                    break
                time.sleep(0.5)

            if not self.connected and not self._shutdown_requested:
                self.logger.warning(
                    "OffPeakClient : timeout connexion WebSocket, planification reconnexion."
                )
                self._schedule_reconnect()

        except Exception as e:
            self.logger.error(
                f"OffPeakClient : erreur connexion WebSocket : {str(e)}"
            )
            self._schedule_reconnect()
        finally:
            with self._lock:
                self._connecting = False

    def _run_ws_forever(self):
        """Wrapper pour run_forever avec gestion d'erreur."""
        try:
            self.ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            self.logger.error(f"OffPeakClient : run_forever terminé avec erreur : {str(e)}")
        finally:
            # Mark as disconnected when run_forever exits
            if not self._shutdown_requested:
                self.connected = False
                self._publish_connection_state(False)
                self._schedule_reconnect()

    def _on_open(self, ws):
        self.connected = True
        self.message_id = 1
        self._last_activity_time = time.time()
        with self._lock:
            self._reconnect_delay = self.INITIAL_RECONNECT_DELAY  # Reset backoff
            self._reconnect_scheduled = False
        self.logger.info("OffPeakClient : connexion WebSocket ouverte.")
        self._publish_connection_state(True)

    def _on_ping(self, ws, data):
        """Callback when a ping frame is received from the server."""
        self._last_activity_time = time.time()
        self.logger.debug("OffPeakClient : ping reçu du serveur.")

    def _on_pong(self, ws, data):
        """Callback when a pong frame is received (response to our ping)."""
        self._last_activity_time = time.time()
        self.logger.debug("OffPeakClient : pong reçu du serveur.")

    def _on_message(self, ws, message):
        self._last_activity_time = time.time()
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

            elif msg_type == "auth_invalid":
                self.logger.error(
                    f"OffPeakClient : authentification échouée - {data.get('message', 'token invalide')}"
                )

            elif msg_type == "result" and data.get("success"):
                # Réponse à get_states : extraction de l'état initial
                result = data.get("result")
                if isinstance(result, list):
                    for entity in result:
                        if entity.get("entity_id") == self.entity_id:
                            self._update_state(entity.get("state"), source="WebSocket")
                            break

            elif msg_type == "event":
                event_data = data.get("event", {}).get("data", {})
                entity_id = event_data.get("entity_id")
                if entity_id == self.entity_id:
                    new_state = event_data.get("new_state", {}).get("state")
                    self._update_state(new_state, source="WebSocket")

            elif msg_type == "pong":
                pass  # Ping/pong for keepalive

        except Exception as e:
            self.logger.error(
                f"OffPeakClient : erreur traitement message : {str(e)}"
            )

    def _on_error(self, ws, error):
        was_connected = self.connected
        self.connected = False
        self._is_off_peak = False  # Fallback conservateur → HP
        self.logger.error(f"OffPeakClient : erreur WebSocket : {str(error)}")
        if was_connected:
            self._publish_connection_state(False)
        self._schedule_reconnect()

    def _on_close(self, ws, close_status_code, close_msg):
        was_connected = self.connected
        self.connected = False
        self._is_off_peak = False  # Fallback conservateur → HP
        self.logger.info(
            f"OffPeakClient : WebSocket fermée : {close_status_code} - {close_msg}"
        )
        if was_connected:
            self._publish_connection_state(False)
        self._schedule_reconnect()

    def _force_reconnect(self):
        """Force la fermeture et reconnexion (si pas déjà en cours)."""
        with self._lock:
            if self._connecting or self._reconnect_scheduled:
                self.logger.debug("OffPeakClient : reconnexion déjà en cours, ignoré.")
                return
        self.logger.info("OffPeakClient : forçage reconnexion...")
        self.connected = False
        self._publish_connection_state(False)
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Planifie une reconnexion avec backoff exponentiel (thread-safe)."""
        if self._shutdown_requested:
            return

        with self._lock:
            if self._reconnect_scheduled or self._connecting:
                return
            self._reconnect_scheduled = True
            delay = self._reconnect_delay
            self._reconnect_delay = min(delay * 2, self.MAX_RECONNECT_DELAY)

        self.logger.info(f"OffPeakClient : reconnexion dans {delay}s...")

        def _do_reconnect():
            time.sleep(delay)
            if self._shutdown_requested:
                with self._lock:
                    self._reconnect_scheduled = False
                return
            with self._lock:
                self._reconnect_scheduled = False
            if not self._shutdown_requested:
                self._connect_websocket()

        t = threading.Thread(target=_do_reconnect, name="OffPeakReconnect")
        t.daemon = True
        t.start()

    def _publish_connection_state(self, connected):
        """Publie l'état de connexion sur MQTT si disponible."""
        if self.mqtt_handler:
            try:
                self.mqtt_handler.publish_off_peak_connection_state(connected)
            except AttributeError:
                pass  # Method may not exist yet
            except Exception as e:
                self.logger.debug(f"OffPeakClient : erreur publication état connexion : {str(e)}")

    def _request_initial_state(self):
        """Récupère l'état initial via get_states."""
        try:
            request = {
                "id": self.message_id,
                "type": "get_states",
            }
            self.ws.send(json.dumps(request))
            self.message_id += 1
        except Exception as e:
            self.logger.error(f"OffPeakClient : erreur envoi get_states : {str(e)}")

    def _subscribe_state_changes(self):
        """Souscrit aux changements d'état via state_changed."""
        try:
            request = {
                "id": self.message_id,
                "type": "subscribe_events",
                "event_type": "state_changed",
            }
            self.ws.send(json.dumps(request))
            self.message_id += 1
        except Exception as e:
            self.logger.error(f"OffPeakClient : erreur souscription state_changed : {str(e)}")

    def _update_state(self, state, source="unknown"):
        """Met à jour l'état HC/HP et publie sur MQTT si disponible."""
        previous = self._is_off_peak
        self._is_off_peak = (state == "on")
        self._state_received = True

        label = "HC (off-peak)" if self._is_off_peak else "HP (peak)"
        self.logger.info(f"OffPeakClient ({source}) : état mis à jour → {label}")

        if self._is_off_peak != previous and self.mqtt_handler:
            self.mqtt_handler.publish_off_peak_state(self._is_off_peak)

    def is_off_peak(self):
        """Retourne True si HC, False si HP. Fallback : False (conservateur)."""
        return self._is_off_peak

    def is_connected(self):
        """Retourne True si la connexion WebSocket est active."""
        return self.connected

    def shutdown(self):
        """Arrête proprement le client et tous ses threads daemon."""
        self._shutdown_requested = True
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        # Wait for threads to finish (with short timeouts since they're daemon threads)
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=2.0)
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=1.0)
        if self._rest_fallback_thread and self._rest_fallback_thread.is_alive():
            self._rest_fallback_thread.join(timeout=1.0)
        self.logger.info("OffPeakClient arrêté.")

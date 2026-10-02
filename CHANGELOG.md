# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

**À partir de la version 2026.10.2**, ce projet utilise [CalVer](https://calver.org/) 
(Calendar Versioning) au format `YYYY.M.D` (année.mois.jour, sans padding de zéros).
Les versions précédentes utilisaient le versionnage sémantique (3.x.x).

## [Unreleased]

### Corrigé

- **Erreurs de conversion de payloads MQTT vides** : Les topics de commande numériques
  (`yutampo/number/.../set` et `yutampo/climate/.../set`) ignorent désormais les
  payloads vides ou composés uniquement d'espaces avec un log de niveau debug. Les
  payloads non numériques sont ignorés avec un warning simple au lieu d'une erreur
  avec stack trace. Corrige les erreurs "could not convert string to float: ''" qui
  apparaissaient au démarrage lors de la réception de messages retenus vides (utilisés
  pour effacer les messages retenus précédents).

## [2026.10.2] - 2026-10-02

### Corrigé

- **Bug critique de reconnexion WebSocket** : Après un redémarrage de Home Assistant,
  le client OffPeak ne se reconnectait jamais au WebSocket HA. Le problème était une
  race condition où `_reconnecting` restait à `True` si `run_forever` échouait pendant
  l'attente de connexion (5s), bloquant toute tentative de reconnexion ultérieure
  déclenchée par `_on_error` ou `_on_close`. L'état `_is_off_peak` restait figé à
  `False` (heures pleines) indéfiniment, empêchant la régulation d'appliquer la
  consigne maximale pendant les heures creuses.

- **Oscillation de consigne 37.5°C/37°C** : Utilisation de `round()` au lieu de `int()`
  pour arrondir la température DHW avant envoi à l'API. Avec `int()`, une consigne de
  37.5°C était tronquée à 37°C, mais l'état MQTT conservait 37.5°C, provoquant un
  renvoi de commande toutes les 5 minutes. La fonction `set_heat_setting()` retourne
  maintenant la température arrondie effectivement appliquée pour que les appelants
  mettent à jour leur état local de manière cohérente.

### Ajouté

- **Watchdog de connexion** : Un thread surveille la connexion WebSocket et force une
  reconnexion si aucune activité (message ou pong) pendant 2 minutes (`WATCHDOG_TIMEOUT`).
  Utilise les callbacks `on_ping`/`on_pong` de websocket-client pour éviter les faux
  positifs quand seuls des pings/pongs circulent (pas de state_changed pendant 2 min).

- **Fallback REST** : Quand le WebSocket est déconnecté ou qu'aucun état n'a été reçu,
  le client récupère périodiquement l'état de l'entité HC/HP via l'API REST
  `/api/states/<entity>` (toutes les 60 secondes), garantissant que la régulation
  fonctionne même en cas de problème WebSocket.

- **Capteur de santé de connexion** : Nouvelle entité `binary_sensor.yutampo_off_peak_connected`
  exposée via MQTT Discovery. Indique si le client WebSocket OffPeak est connecté à
  Home Assistant (`ON`) ou déconnecté (`OFF`). Permet de surveiller la santé de
  l'intégration et de créer des alertes.

- **Tests unitaires** : 19 nouveaux tests couvrant :
  - La race condition de reconnexion
  - Le backoff exponentiel (5s → 10s → 20s... max 60s)
  - Le watchdog et la détection de connexion silencieuse
  - Le fallback REST (succès, erreur HTTP, timeout)
  - L'état de connexion (`is_connected()`)
  - La discovery MQTT du capteur de connexion
  - L'arrondi de température avec `round()` vs `int()`
  - L'absence d'oscillation après correction

### Modifié

- **Délai max de reconnexion** : Réduit de 300s (5 min) à 60s pour une reprise plus
  rapide après un redémarrage de HA.

- **Thread safety améliorée** : Flag `_connecting` avec verrou pour éviter les
  tentatives de connexion WebSocket concurrentes. `shutdown()` attend proprement
  les threads watchdog et REST en plus du thread WebSocket.

- **Logging amélioré** : Messages de log plus explicites lors des déconnexions,
  reconnexions, et récupérations d'état via REST, incluant la source de la mise à
  jour (`WebSocket` ou `REST`).

- **Migration CalVer** : Passage au versionnage basé sur la date (YYYY.M.D) pour
  une meilleure traçabilité temporelle des releases.

## [3.7.7] - 2026-09-28

### Corrigé

- Correction de l'écrasement des valeurs MQTT retenues lors du redémarrage de l'addon.

## [3.7.6] - 2026-09-27

### Corrigé

- Correction du bug de poursuite de fenêtre météo quand les prévisions se mettent
  à jour avec des heures passées.

### Ajouté

- Tests unitaires pour la fenêtre de chauffe et la discovery OffPeak.

## [3.7.5] - 2026-09-26

### Corrigé

- Fermeture des sessions/websockets avant reconnexion pour éviter les fuites de
  descripteurs de fichiers.

---

Pour les versions antérieures, consultez l'historique git.

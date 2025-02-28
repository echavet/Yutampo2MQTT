#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Lancement de l'add-on Yutampo..."

# Récupération des informations MQTT depuis l'intégration HA via bashio

if ! bashio::services.available "mqtt"; then
    bashio::log.error "No internal MQTT service found"
else
    bashio::log.info "MQTT service found, fetching credentials ..."
    MQTT_HOST=$(bashio::services mqtt "host")
    MQTT_USER=$(bashio::services mqtt "username")
    MQTT_PASSWORD=$(bashio::services mqtt "password")
    MQTT_PORT=$(bashio::services mqtt "port")
fi

# Exportation des variables dans l'environnement
export MQTT_HOST
export MQTT_PORT
export MQTT_USER
export MQTT_PASSWORD

# Logs pour déboguer
echo "MQTT_HOST: $MQTT_HOST"
echo "MQTT_PORT: $MQTT_PORT"
echo "MQTT_USER: $MQTT_USER"
echo "MQTT_PASSWORD: [masked]"

# Lancement du script Python
python3 /app/main.py

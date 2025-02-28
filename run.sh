#!/usr/bin/with-contenv bashio
set -e

echo "Lancement de l'add-on Yutampo..."

# Récupération des informations MQTT depuis l'intégration HA via bashio
MQTT_HOST=$(bashio::services mqtt "host")
MQTT_PORT=$(bashio::services mqtt "port")
MQTT_USER=$(bashio::services mqtt "username")
MQTT_PASSWORD=$(bashio::services mqtt "password")

# Vérification que les valeurs sont bien récupérées
if [ -z "$MQTT_HOST" ] || [ -z "$MQTT_PORT" ] || [ -z "$MQTT_USER" ] || [ -z "$MQTT_PASSWORD" ]; then
    echo "Erreur : Impossible de récupérer les informations MQTT depuis Home Assistant."
    echo "MQTT_HOST=$MQTT_HOST, MQTT_PORT=$MQTT_PORT, MQTT_USER=$MQTT_USER, MQTT_PASSWORD=[masked]"
    exit 1
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

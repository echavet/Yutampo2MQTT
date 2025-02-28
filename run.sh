#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Lancement de l'add-on Yutampo..."

# Récupération des informations MQTT depuis l'intégration HA via bashio

export MQTTHOST=$(bashio::config "mqtt_host")
export MQTTPORT=$(bashio::config "mqtt_port")
export MQTTUSER=$(bashio::config "mqtt_user")
export MQTTPASSWORD=$(bashio::config "mqtt_password")

if [ $MQTTHOST = '<auto_detect>' ]; then
    if bashio::services.available 'mqtt'; then
        MQTTHOST=$(bashio::services mqtt "host")
	if [ $MQTTHOST = 'localhost' ] || [ $MQTTHOST = '127.0.0.1' ]; then	    
     	    bashio::log.debug "Discovered invalid value for MQTT host: ${MQTTHOST}"
	    bashio::log.debug "Overriding with default alias for Mosquitto MQTT addon"	    
	    MQTTHOST="core-mosquitto"
	fi
        bashio::log.info "Using discovered MQTT Host: ${MQTTHOST}"
    else
    	bashio::log.warning "No Home Assistant MQTT service found, using defaults"
        MQTTHOST="172.30.32.1"
        bashio::log.info "Using default MQTT Host: ${MQTTHOST}"
    fi
else
    bashio::log.info "Using configured MQTT Host: ${MQTTHOST}"
fi

if [ $MQTTPORT = '<auto_detect>' ]; then
    if bashio::services.available 'mqtt'; then
        MQTTPORT=$(bashio::services mqtt "port")
        bashio::log.info "Using discovered MQTT Port: ${MQTTPORT}"
    else
        MQTTPORT="1883"
        bashio::log.info "Using default MQTT Port: ${MQTTPORT}"
    fi
else
    bashio::log.info "Using configured MQTT Port: ${MQTTPORT}"
fi

if [ $MQTTUSER = '<auto_detect>' ]; then
    if bashio::services.available 'mqtt'; then
        MQTTUSER=$(bashio::services mqtt "username")
        bashio::log.info "Using discovered MQTT User: ${MQTTUSER}"
    else
        MQTTUSER=""
        bashio::log.info "Using anonymous MQTT connection"
    fi
else
    bashio::log.info "Using configured MQTT User: ${MQTTUSER}"
fi

if [ $MQTTPASSWORD = '<auto_detect>' ]; then
    if bashio::services.available 'mqtt'; then
        MQTTPASSWORD=$(bashio::services mqtt "password")
        bashio::log.info "Using discovered MQTT password: ${MQTTPASSWORD}"
    else
        MQTTPASSWORD=""
    fi
else
    bashio::log.info "Using configured MQTT password: <hidden>"
fi

# Lancement du script Python
python3 /app/main.py

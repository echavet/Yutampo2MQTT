ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Installation des dépendances Alpine
RUN apk add --no-cache python3 py3-pip py3-requests py3-beautifulsoup4 py3-voluptuous py3-apscheduler py3-paho-mqtt py3-aiohttp py3-websocket-client

# Créer le répertoire pour les logs
RUN mkdir -p /var/log/yutampo && chmod 755 /var/log/yutampo

# Définition du répertoire de travail
WORKDIR /app

# Copie du code source
COPY . /app

# Copie des fichiers de service s6-overlay
COPY s6-services /etc/s6-overlay/s6-rc.d/

# Copie du wrapper
COPY run-wrapper.sh /app/run-wrapper.sh

# Rendre les scripts exécutables
RUN chmod +x /app/run.sh && \
    chmod +x /app/run-wrapper.sh && \
    chmod +x /etc/s6-overlay/s6-rc.d/yutampo/run && \
    chmod +x /etc/s6-overlay/s6-rc.d/yutampo-log/run

# Pas de CMD, s6-overlay exécutera les services définis
CMD [ "/bin/true" ]
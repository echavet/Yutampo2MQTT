ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Installation des dépendances Alpine
RUN apk add --no-cache python3 py3-pip py3-requests py3-beautifulsoup4 py3-voluptuous py3-apscheduler

# Définition du répertoire de travail
WORKDIR /app

# Copie du code source
COPY . /app

# Exécution du script principal
CMD ["python3", "/app/main.py"]

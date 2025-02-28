ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Installation des dépendances
RUN apk add --no-cache python3 py3-pip

# Copie du code source
WORKDIR /app
COPY . /app

# Installation des dépendances Python
RUN pip3 install -r requirements.txt

# Exécution du script principal
CMD ["python3", "/app/main.py"]

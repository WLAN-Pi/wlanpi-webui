# CERTS 

Examples for generating self signed certificates.

## WEBUI

Generating a self signed certificate for the Web UI:

```bash
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 \
  -nodes -keyout self-signed-wlanpi.key -out self-signed-wlanpi.cert -subj "/CN=wlanpi.local" \
  -addext "subjectAltName=DNS:wlanpi.local,DNS:*.wlanpi.local,IP:127.0.0.1"
```

## GRAFANA

```bash
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 \
  -nodes -keyout self-signed-grafana.key -out self-signed-grafana.cert -subj "/CN=grafana.wlanpi.local" \
  -addext "subjectAltName=DNS:grafana.wlanpi.local,DNS:*.grafana.wlanpi.local,IP:127.0.0.1"
```

Grafana group needs permissions to access the certs.

```bash
sudo chgrp -R grafana self-signed-grafana.key 
sudo chgrp -R grafana self-signed-grafana.cert 
sudo chmod -R g+rx self-signed-grafana.key
sudo chmod -R g+rx self-signed-grafana.cert
```

## KISMET

Generating a self signed certificate for Kismet:

```bash
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 \
  -nodes -keyout kismet-wlanpi.pem -out kismet-wlanpi.cert -subj "/CN=kismet.wlanpi.local" \
  -addext "subjectAltName=DNS:kismet.wlanpi.local,DNS:*.kismet.wlanpi.local,IP:127.0.0.1"
```

Verify file is a PEM:

```bash
sudo openssl rsa -inform PEM -in kismet-wlanpi.pem 
```
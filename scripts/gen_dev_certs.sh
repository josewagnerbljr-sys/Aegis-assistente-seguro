#!/bin/sh
# Certificado autoassinado SOMENTE para desenvolvimento. Em produção use ACME/Let's Encrypt ou a CA da empresa.
set -eu
mkdir -p deploy/certs
openssl req -x509 -newkey rsa:3072 -nodes -days 30 -subj "/CN=localhost" \
  -keyout deploy/certs/tls.key -out deploy/certs/tls.crt
chmod 600 deploy/certs/tls.key
echo "ok: deploy/certs/tls.crt"

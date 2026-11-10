#!/bin/sh
# Builds Mosquitto's password file from the passwords in .env, copies the ACL with private permissions,
# then starts the broker.
set -eu
mkdir -p /mosquitto/run
PASSWD=/mosquitto/run/passwd
: > "$PASSWD"
chmod 0700 "$PASSWD"
mosquitto_passwd -b "$PASSWD" devices "$MQTT_DEVICE_PASSWORD"
mosquitto_passwd -b "$PASSWD" ingest "$MQTT_INGEST_PASSWORD"
cp /mosquitto/config/acl /mosquitto/run/acl
chmod 0700 /mosquitto/run/acl
chown -R mosquitto:mosquitto /mosquitto/run /mosquitto/data
exec mosquitto -c /mosquitto/config/mosquitto.conf

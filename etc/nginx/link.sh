#!/bin/bash

mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
rm /etc/nginx/sites-enabled/default
ln -s /etc/wlanpi-webui/nginx/nginx.conf /etc/nginx/nginx.conf
ln -s /etc/wlanpi-webui/nginx/sites-enabled/wlanpi_speedtest.conf /etc/nginx/sites-enabled/wlanpi_speedtest.conf
ln -s /etc/wlanpi-webui/nginx/sites-enabled/wlanpi_webui.conf /etc/nginx/sites-enabled/wlanpi_webui.conf
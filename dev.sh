unlink /etc/nginx/sites-enabled/wlanpi_webui.conf
ln -s /home/wlanpi/wlanpi-webui/install/etc/nginx/wlanpi_webui.conf /etc/nginx/sites-enabled/wlanpi_webui.conf
systemctl restart wlanpi-webui
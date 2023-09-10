unlink /etc/nginx/sites-enabled/wlanpi_webui.conf
ln -s /home/wlanpi/wlanpi-webui/install/etc/nginx/wlanpi_webui.conf /etc/nginx/sites-enabled/wlanpi_webui.conf
unlink /etc/nginx/sites-enabled/wlanpi_librespeed.conf
ln -s /home/wlanpi/wlanpi-webui/install/etc/nginx/wlanpi_librespeed.conf /etc/nginx/sites-enabled/wlanpi_librespeed.conf
systemctl restart wlanpi-webui
systemctl restart nginx
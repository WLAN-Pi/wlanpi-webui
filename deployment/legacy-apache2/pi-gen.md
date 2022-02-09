# wlanpi-webui and pi-gen

This note describes the dependencies outside of the debianization of wlanpi-webui.

RBPi based units will be using pi-gen which will install wlanpi-webui from a cloud repo.

## freeing up and disabling services that may conflict

for development:

```
# disable apache2
systemctl stop apache2
systemctl disable apache2
```

this may be solved by simply not installing these services by default.

## nginx config

`postinst` is handling nginx configuration linking.

## user

`wlanpi-webui` expects to be run as `www-data` and needs set up if it is not included by default, but it _should_ be there by default.

## ufw

pi-gen will add ufw rules to ensure the needed ports are allowed:

- TCP 80 - flask
- TCP 8080 - speedtest
- TCP 9090 - cockpit 

https://github.com/WLAN-Pi/pi-gen/blob/master/wlanpi1/01-config-files/files/etc/ufw/user.rules
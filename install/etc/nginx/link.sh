#!/bin/bash

function isValidSymlink() {
    if [ -L "$1" ]; then
        return 0
    else
        return 1
    fi
}

# if conf is not a symlink, create backup.
NGINX_CONF=/etc/nginx/nginx.conf
if ! isValidSymlink $NGINX_CONF; then
    if [ -f "$NGINX_CONF" ]; then
        TSTAMP=`date '+%s'`
        NEW_CONF="$NGINX_CONF.$TSTAMP"
        echo "Existing nginx.conf detected; moving to $NEW_CONF..."
        mv $NGINX_CONF $NEW_CONF
    fi
    echo "Linking our nginx.conf config..."
    ln -s /etc/wlanpi-webui/nginx/nginx.conf $NGINX_CONF
fi

# if default site is enabled, disable it.
DEFAULT_FILE=/etc/nginx/sites-enabled/default
if isValidSymlink $DEFAULT_FILE; then
    echo "Unlinking $DEFAULT_FILE"
    unlink $DEFAULT_FILE
fi

WLANPI_LIBRESPEED=/etc/nginx/sites-enabled/wlanpi_librespeed.conf

if ! isValidSymlink $WLANPI_LIBRESPEED; then
    echo "Linking wlanpi_librespeed.conf..."
    ln -s /etc/wlanpi-webui/nginx/sites-enabled/wlanpi_librespeed.conf $WLANPI_LIBRESPEED
fi

WLANPI_WEBUI=/etc/nginx/sites-enabled/wlanpi_webui.conf

if ! isValidSymlink $WLANPI_WEBUI; then
    echo "Linking wlanpi_webui.conf..."
    ln -s /etc/wlanpi-webui/nginx/sites-enabled/wlanpi_webui.conf $WLANPI_WEBUI
fi

nginx -t

systemctl restart nginx.service
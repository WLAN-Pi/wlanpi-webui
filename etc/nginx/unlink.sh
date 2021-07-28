#!/bin/bash
# unlink our symlinks if they exist

function unlink_if_existing() {
    if [ -L "$1" ]; then
        unlink $1
    fi
}

unlink_if_existing /etc/nginx/nginx.conf
unlink_if_existing /etc/nginx/sites-enabled/wlanpi_speedtest.conf
unlink_if_existing /etc/nginx/sites-enabled/wlanpi_webui.conf

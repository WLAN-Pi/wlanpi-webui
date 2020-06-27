#!/bin/bash
# wlanpi-webui setup script

# we need root permissions to run
if [[ $EUID -ne 0 ]]; then
    echo "Need run with root permissions"
    exit 1
fi

REPO="https://github.com/joshschmelzle/wlanpi-webui.git"
REPONAME="wlanpi-webui"
WLANPIDIR="/opt/wlanpi2"
USER="wlanpi"

if [[ -d "$WLANPIDIR" ]]; then
    echo "$WLANPIDIR already exists... skipping..."
else
    echo "creating $WLANPIDIR and changing owner to $USER..." 
    sudo mkdir $WLANPIDIR
fi

if [[ -d "$WLANPIDIR/$REPONAME" ]]; then
    echo "$WLANPIDIR/$REPONAME already exists... skipping..."
else
    git clone $REPO $WLANPIDIR/$REPONAME
fi

activate () {
    . $WLANPIDIR/$REPONAME/venv/bin/activate
}

if [[ -d "$WLANPIDIR/$REPONAME/venv" ]]; then
    echo "$WLANPIDIR/$REPONAME/venv already exists... skipping..."
else
    sudo -u wlanpi python3 -m virtualenv -p=python3 $WLANPIDIR/$REPONAME/venv
    activate
    pip install -r $WLANPIDIR/$REPONAME/requirements.txt
    pip install $WLANPIDIR/$REPONAME/.
    deactivate
fi

# PHP

PHP_PKG="php"
PKG_OK=$(dpkg-query -W --showformat='${Status}\n' $PHP_PKG | grep "install ok installed")
echo "checking for $PHP_PKG: $PKG_OK"
if [[ "" = "$PKG_OK" ]]; then
    echo "$PHP_PKG not installed. Setting up $PHP_PKG..."
    apt --yes install php
fi

# APACHE2 

MOD_WSGI_PKG="libapache2-mod-wsgi-py3"
PKG_OK=$(dpkg-query -W --showformat='${Status}\n' $MOD_WSGI_PKG | grep "install ok installed")
echo "checking for $MOD_WSGI_PKG: $PKG_OK"
if [[ "" = "$PKG_OK" ]]; then
    echo "$MOD_WSGI_PKG not installed. Setting up $MOD_WSGI_PKG..."
    apt --yes install libapache2-mod-wsgi-py3
    sudo a2enmod wsgi
fi

APACHE_CONF="wlanpi-webui.conf"

if [[ ! -f /etc/apache2/sites-available/$APACHE_CONF ]]; then
    cp $WLANPIDIR/$REPONAME/$APACHE_CONF /etc/apache2/sites-avilable/$APACHE_CONF
fi

sudo chown -R $USER:$USER $WLANPIDIR

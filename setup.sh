#!/bin/bash
# wlanpi-webui setup script

# we need root permissions to run
if [[ $EUID -ne 0 ]]; then
    echo "Need run with root permissions"
    exit 1
fi

echo "start..."

# MAIN APP

REPO="https://github.com/joshschmelzle/wlanpi-webui.git"
REPONAME="wlanpi-webui"
WLANPIDIR="/opt/wlanpi"
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
    sudo chown -R $USER:$USER $WLANPIDIR
    sudo -u $USER python3 -m virtualenv -p=python3 $WLANPIDIR/$REPONAME/venv
    activate
    pip install -r $WLANPIDIR/$REPONAME/requirements.txt
    pip install $WLANPIDIR/$REPONAME/.
    deactivate
fi

# SPEEDTEST APP

SPEEDTESTDIR="/var/www/wlanpi-speedtest"
WWW="www-data" 
 
if [[ -d "$SPEEDTESTDIR" ]]; then
    echo "$SPEEDTESTDIR already exists... skipping..."
else
    echo "creating $SPEEDTESTDIR..."
    sudo mkdir $SPEEDTESTDIR
    echo "copying files to $SPEEDTESTDIR..."
    cp $WLANPIDIR/$REPONAME/speedtest/src/* $SPEEDTESTDIR -r
    echo "changing $SPEEDTESTDIR owner to $WWW"
    sudo chown -R $WWW:$WWW $SPEEDTESTDIR
fi


if [[ -d "$WLANPIDIR/$REPONAME" ]]; then
    echo "$WLANPIDIR/$REPONAME already exists... skipping..."
else
    git clone $REPO $WLANPIDIR/$REPONAME
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
    cp $WLANPIDIR/$REPONAME/$APACHE_CONF /etc/apache2/sites-available/$APACHE_CONF
fi

SPEED_CONF="wlanpi-speedtest.conf"
if [[ ! -f /etc/apache2/sites-available/$SPEED_CONF ]]; then
    cp $WLANPIDIR/$REPONAME/$SPEED_CONF /etc/apache2/sites-available/$SPEED_CONF
fi

# APACHE2 NEEDS TO LISTEN ON 8080!

PCONF=`grep -r "Listen 8080" /etc/apache2/ports.conf`
if [[ "" = "$PCONF" ]]; then
    echo "Adding 8080 to /etc/apache2/ports.conf"
    echo 'Listen 8080' >> /etc/apache2/ports.conf
fi

# TURN UP

a2dissite 000-default.conf
a2ensite wlanpi-webui.conf
a2ensite wlanpi-speedtest.conf

# PERMISSIONS!

echo "making sure $WLANPIDIR owner is $USER..."
sudo chown -R $USER:$USER $WLANPIDIR

# REBOOT APACHE

echo "restarting apache2..."
sudo systemctl restart apache2

echo "done..."

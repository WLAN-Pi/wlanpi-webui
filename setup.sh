#!/bin/bash
# wlanpi-webui setup script

# we need root permissions to run
if [[ $EUID -ne 0 ]]; then
    echo "Need run with root permissions"
    exit 1
fi

echo "start..."

# MAIN APP

webui_repo="https://github.com/joshschmelzle/wlanpi-webui.git"
webui_repo_name="wlanpi-webui"
app_dir="/opt/wlanpi"
user="wlanpi"

if [[ -d "$app_dir" ]]; then
    echo "$app_dir already exists... skipping..."
else
    echo "creating $app_dir and changing owner to $USER..." 
    sudo mkdir $app_dir
fi

if [[ -d "$app_dir/$webui_repo_name" ]]; then
    echo "$app_dir/$webui_repo_name already exists... skipping..."
else
    git clone $webui_repo $app_dir/$webui_repo_name
fi

activate () {
    . $app_dir/$webui_repo_name/venv/bin/activate
}

if [[ -d "$app_dir/$webui_repo_name/venv" ]]; then
    echo "$app_dir/$webui_repo_name/venv already exists... skipping..."
else
    sudo chown -R $user:$user $app_dir
    sudo -u $user python3 -m virtualenv -p=python3 $app_dir/$webui_repo_name/venv
    activate
    pip install -r $app_dir/$webui_repo_name/requirements.txt
    pip install $app_dir/$webui_repo_name/.
    deactivate
fi

# SPEEDTEST APP

speedtest_dir="/var/www/wlanpi-speedtest"
www_user="www-data" 
 
if [[ -d "$speedtest_dir" ]]; then
    echo "$speedtest_dir already exists... skipping..."
else
    echo "creating $speedtest_dir..."
    sudo mkdir $speedtest_dir
    echo "copying files to $speedtest_dir..."
    cp $app_dir/$webui_repo_name/speedtest/src/* $speedtest_dir -r
    echo "changing $speedtest_dir owner to $www_user"
    sudo chown -R $www_user:$www_user $speedtest_dir
fi

# PHP

php_pkg="php"
pkg_ok=$(dpkg-query -W --showformat='${Status}\n' $php_pkg | grep "install ok installed")
echo "checking for $php_pkg: $pkg_ok"
if [[ "" = "$pkg_ok" ]]; then
    echo "$pkg_ok not installed. Setting up $php_pkg..."
    apt --yes install php
fi

# APACHE2 

mod_wsgi_pkg="libapache2-mod-wsgi-py3"
pkg_ok=$(dpkg-query -W --showformat='${Status}\n' $mod_wsgi_pkg | grep "install ok installed")
echo "checking for $mod_wsgi_pkg: $pkg_ok"
if [[ "" = "$pkg_ok" ]]; then
    echo "$mod_wsgi_pkg not installed. Setting up $mod_wsgi_pkg..."
    apt --yes install libapache2-mod-wsgi-py3
    sudo a2enmod wsgi
fi

webui_app_conf="wlanpi-webui.conf"
if [[ ! -f /etc/apache2/sites-available/$webui_app_conf ]]; then
    cp $app_dir/$webui_repo_name/$webui_app_conf /etc/apache2/sites-available/$webui_app_conf
fi

webui_speedtest_conf="wlanpi-speedtest.conf"
if [[ ! -f /etc/apache2/sites-available/$webui_speedtest_conf ]]; then
    cp $app_dir/$webui_repo_name/$webui_speedtest_conf /etc/apache2/sites-available/$webui_speedtest_conf
fi

# APACHE2 NEEDS TO LISTEN ON 8080!

ports=`grep -r "Listen 8080" /etc/apache2/ports.conf`
if [[ "" = "$ports" ]]; then
    echo "Adding 8080 to /etc/apache2/ports.conf"
    echo 'Listen 8080' >> /etc/apache2/ports.conf
fi

# UFW NEEDS TO ALLOW 8080

ufw=`ufw status numbered | grep 8080`
if [[ "" = "$ufw" ]]; then
    echo "Punching a hole in the firewall (ง •̀_•́)ง..."
    ufw allow 8080
fi 

# TURN UP

a2dissite 000-default.conf
a2ensite wlanpi-webui.conf
a2ensite wlanpi-speedtest.conf

# PERMISSIONS!

echo "making sure $WLANPIDIR owner is $user..."
sudo chown -R $user:$user $app_dir

# PATCH REACHABILITY SCRIPT
 
reachability="/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/reachability.sh"
ipconfig="/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/ipconfig.sh"

if [[ -f reachability ]]; then
    rm reachability
fi   
cp $app_dir/$webui_repo_name/fpms/reachability.sh reachability

if [[ -f ipconfig ]]; then
    rm ipconfig
fi 
cp $app_dir/$webui_repo_name/fpms/ipconfig.sh ipconfig

sudo chmod +s /usr/bin/arping

# REBOOT APACHE

echo "restarting apache2..."
sudo systemctl restart apache2

echo "done..."

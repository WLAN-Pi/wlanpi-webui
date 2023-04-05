#!/bin/bash

Main() {
	SetupPipxEnviro
    InstallPipx
    SetupWebui
}

SetupPipxEnviro() {
	display_alert "Setup Pipx Environment" "" "info"
    # Setting up Pipx in a global directory so all users in sudo group can access installed packages
	mkdir -p /opt/wlanpi/pipx/bin
	chown -R root:sudo /opt/wlanpi/pipx
	chmod -R g+rwx /opt/wlanpi/pipx
	cat <<EOF >> /etc/environment
PIPX_HOME=/opt/wlanpi/pipx
PIPX_BIN_DIR=/opt/wlanpi/pipx/bin
EOF
	# Set pipx variables for the remainder of the script
	export PIPX_HOME=/opt/wlanpi/pipx
	export PIPX_BIN_DIR=/opt/wlanpi/pipx/bin
}

InstallPipx() {
    display_alert "Installing Pipx" "" "info"	
    # Install a deterministic version of pipx
	python3 -m pip install pipx==0.15.4.0
}

SetupWebui() {
    display_alert "Installing WebUI" "" "info"
    # install with pip via pipx
	pipx install --include-deps git+https://github.com/joshschmelzle/wlanpi-webui@1.0.0-b3-2#egg=wlanpi_webui
   
    # setup config required to support the webui
    git clone -b dev https://github.com/joshschmelzle/wlanpi-webui.git 

    # disable apache2
    systemctl stop apache2
    systemctl disable apache2

    # install nginx php
    apt install nginx-light php7.4-fpm -y
     
    # need to modify php fpm stuff (/etc/php/7.4/fpm) 
    cp -a ./wlanpi-webui/deployment/php/php.ini /etc/php/7.4/fpm

    # setup speedtest    
    mkdir -p /var/www/speedtest
    cp -ra ./wlanpi-webui/speedtest/src/* /var/www/speedtest
    chown -R www-data:www-data /var/www/speedtest

    # rm default nginx config
    rm /etc/nginx/sites-enabled/default

    # setup nginx config
    cp -a ./wlanpi-webui/deployment/nginx/nginx.conf /etc/nginx   
 
    # add sites-enabled configs 
    cp -a ./wlanpi-webui/deployment/nginx/wlanpi* /etc/nginx/sites-enabled
   
    # services
    install -o wlanpi -g wlanpi -m 644 ./wlanpi-webui/deployment/systemd/wlanpi_webui.s* /lib/systemd/system	

    # test nginx config
    nginx -t

    # enable wlanpi_webui service
    systemctl enable wlanpi_webui.service

    # need to add 8080 to ufw rules
    ufw allow 8080

    rm -rf wlanpi-webui
}

display_alert()
{
	# log function parameters to install.log
	[[ -n $DEST ]] && echo "Displaying message: $@" >> $DEST/debug/output.log

	local tmp=""
	[[ -n $2 ]] && tmp="[\e[0;33m $2 \x1B[0m]"

	case $3 in
		err)
		echo -e "[\e[0;31m error \x1B[0m] $1 $tmp"
		;;

		wrn)
		echo -e "[\e[0;35m warn \x1B[0m] $1 $tmp"
		;;

		ext)
		echo -e "[\e[0;32m o.k. \x1B[0m] \e[1;32m$1\x1B[0m $tmp"
		;;

		info)
		echo -e "[\e[0;32m o.k. \x1B[0m] $1 $tmp"
		;;

		*)
		echo -e "[\e[0;32m .... \x1B[0m] $1 $tmp"
		;;
	esac
}

Main "$@"

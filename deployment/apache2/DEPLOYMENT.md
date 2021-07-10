# Requirements

- WLAN Pi v2.0 or higher image. This does not work on the v1.9 build.

# Instructions

1. Make `wlanpi` dir in `/opt` 

```
sudo mkdir /opt/wlanpi
sudo chown $USER /opt/wlanpi
```

2. Clone repo into `/opt/wlanpi`:

```
git clone git@github.com:wlan-pi/wlanpi-webui.git /opt/wlanpi/wlanpi-webui
```

2. Setup virtualenv and requirements 

```
# cd to root of repo
cd /opt/wlanpi/wlanpi-webui

# create venv
python3 -m virtualenv -p=python3 ./venv

# enter virtual environment
source ./venv/bin/activate

# install app requirements
pip install -r requirements.txt

# DEV install wfe_flask into venv (DO NOT USE THIS FOR PRODUCTION)
pip install -e .

# PROD install wfe_flask into venv
pip install .

# deactivate venv
deactivate
```

## APACHE2 METHOD

a3. Install and enable the Apache2 WSGI mod

```
sudo apt-get install libapache2-mod-wsgi-py3
```

(console output should tell you that it has enabled the WSGI mod, but if it doesn't, do 3a)

a3a. (if required) manually enable WSGI mod

```
sudo a2enmod wsgi
```

a4. If not done already, allow HTTP on the firewall 


5. Create a new site in `/etc/apache2/sites-available/` called `wlanpi-webui.conf`: 

```
sudo vim /etc/apache2/sites-available/wlanpi-webui.conf
```

Add the following:

```
<VirtualHost *>
ServerName localhost
WSGIDaemonProcess flaskapp user=wlanpi group=wlanpi threads=5
 WSGIScriptAlias / /opt/wlanpi/wlanpi-webui/wsgi.py
<Directory /opt/wlanpi/wlanpi-webui/>
 WSGIProcessGroup flaskapp
 WSGIApplicationGroup %{GLOBAL}
 WSGIScriptReloading On
Require all granted
</Directory>
</VirtualHost>
```

6. Disable default site and enable `wlanpi-webui.conf`

```
sudo a2dissite 000-default.conf
sudo a2ensite wlanpi-webui.conf
```

7. Install Speedtest app

make sure php is installed.

```
sudo apt install php
```

### apache2

a7a: add and enable site config in `/etc/apache2/sites-available/`

```
sudo vim /etc/apache2/sites-available/wlanpi-speedtest.conf
```

Add the following:

```
<VirtualHost *:8080>                               
    DocumentRoot /var/www/wlanpi-speedtest         
    ErrorLog ${APACHE_LOG_DIR}/error.log           
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>                                     
```

Make apache2 listen on port 8080:

```
sudo vim /etc/apache2/ports.conf

# Add following line in the ports.conf:

Listen 8080
```

Disable default site and enable speedtest sife:

```
sudo a2dissite 000-default.conf
sudo a2ensite wlanpi-speedtest.conf
```

Restart apache

```
sudo systemctl restart apache2
```

### nginx

n7a:


#### App installation:

p8: production:

```
mkdir /var/www/wlanpi-speedtest
cp /opt/wlanpi/wlanpi-webui/speedtest/src/* /var/www/wlanpi-speedtest -r
```

d8: dev:

```
sudo ln -s /opt/wlanpi/wlanpi-webui/speedtest/src /var/www/wlanpi-speedtest
```

File permissions! Speedtest needs write access!

```
sudo chown -R www-data:www-data /var/www/wlanpi-speedtest/*
```

9:

Ensure firewall is allowing port:

```
sudo ufw allow 8080
```

10. Test

Open a browser and go to the IP address of your WLAN Pi. The WebUI app should be running on port `:80` and the Speedtest server should be running on port `:8080`.


# if you run w/ WSGI app with Apache2 and VENV

make sure you install the package in your VENV referenced by the WSGI config.

# development instructions

two options:

1) manually run like:

```
cd <repo base dir>
python3 -m wlanpi-webui
```

2) use an "editable" venv install:

```
# during deployment:
pip install -e .

# apache2: make a change and save
sudo systemctl restart apache2
```

an "editable" venv install will overwrite the directory in site-packages with a symbolic link to the locations repository, meaning any changes to code in there will automatically be reflected - just reload the page (so long as you're using the development server).

# Troubleshooting:

## apache2

Look at the apache2 error log:

```
tail -f /var/log/apache2/error.log
```

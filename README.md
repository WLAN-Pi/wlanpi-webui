![BSD](https://img.shields.io/badge/license-BSD-green) [![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg)](CODE_OF_CONDUCT.md)
# wlanpi-webui

wlanpi-webui is a WebUI built and designed for the [WLAN Pi](https://github.com/WLAN-Pi).

## Authors

- [@joshschmelzle](https://www.github.com/joshschmelzle)
## OSS

 - [flask](https://github.com/pallets/flask)
 - [librespeed](https://github.com/librespeed/speedtest)
 - [uikit](https://github.com/uikit/uikit)
 - [debian new maintainers' guide](https://www.debian.org/doc/manuals/maint-guide/)
## Stack

Deployment:

- Gunicorn as the WSGI server
- Nginx as a proxy server

Application:

- Python
- Flask

CSS:

- UIKit

## Ports

- `:80` - flask (main WSGI app)
- `:8080` - speedtest (html5 speedtest based on LibreSpeed)
- `:9090` - cockpit (installed separately and handled by the WLAN Pi image build process)
- `:2501` - kismet (installed separately and handled by the WLAN Pi image build process)

## Run Package On WLAN Pi

This package is included in the WLAN Pi image. You do not need to do anything special to use it other than point a web browser to the network address of the WLAN Pi.

### The Gory Details

For the curious, we are using systemd unit files to run and control the processes which make the web UI work.

Check nginx service (used as a proxy):

```bash
  systemctl status nginx
  nginx -t
```

Check wsgi/gunicorn service:

```bash
  systemctl status wlanpi_webui
```

Controlling the services

```bash
  sudo service wlanpi_webui [start|stop|restart]
  sudo service nginx [start|stop|restart]
```

## Run Locally (Development)

Clone the project

```bash
  git clone https://github.com/WLAN-Pi/wlanpi-webui
```

Go to the project directory

```bash
  cd wlanpi-webui
```

Create virtualenv

```bash
  python -m venv venv
```

Activate virtualenv

```bash
  source venv/bin/activate
```

Install dependencies

```bash
  pip install -r requirements
```

Starting the development server

```bash
  gunicorn wlanpi_webui.wsgi:app --bind 0.0.0.0
```

## Build Locally (Development)

On your _build host_, install the build tools (these are only needed on your build host):

```
sudo apt-get install build-essential debhelper devscripts equivs python3-pip python3-all python3-dev python3-setuptools dh-virtualenv
```

Install Python depends:

```
python3 -m pip install mock
```

This is required, otherwise if missing, the tooling will fail when tries to evaluate which tests to run.

From the root directory of this repository run:

```
dpkg-buildpackage -us -uc -b
```

If you are found favorable by the packaging gods, you should see output files at `../wlanpi-webui` like this:

```
(venv) wlanpi@rbpi4b-8gb:[~/dev/wlanpi-webui]: ls ../ | grep wlanpi-webui_
wlanpi-webui_1.0.2b1_arm64.buildinfo
wlanpi-webui_1.0.2b1_arm64.changes
wlanpi-webui_1.0.2b1_arm64.deb
```

Install with dpkg:

```sudo dpkg -i wlanpi-webui_1.0.2b1_arm64.deb 
Selecting previously unselected package wlanpi-webui.
(Reading database ... 77019 files and directories currently installed.)
Preparing to unpack wlanpi-webui_1.0.2b1_arm64.deb ...
Unpacking wlanpi-webui (1.0.2b1) ...
Setting up wlanpi-webui (1.0.2b1) ...
Created symlink /etc/systemd/system/multi-user.target.wants/wlanpi-webui.service → /lib/systemd/system/wlanpi-webui.service.
Created symlink /etc/systemd/system/sockets.target.wants/wlanpi-webui.socket → /lib/systemd/system/wlanpi-webui.socket.
Processing triggers for man-db (2.8.5-2) ...
```

### Debian Package Configuration File Conflicts

Two Debian packages can not share the same configuration files, because of this, we are putting our desired `nginx` configuration files in `/etc/wlanpi-webui/nginx` and symlinking is a dependency handled outside of this package.

#### Example of what happens when there are conflicting config files across packages

When we have a conflicting configuration file we get someting like this:

```
dpkg: error processing archive /home/wlanpi/dev/wlanpi-webui_1.0.2b1_arm64.deb (--unpack):
 trying to overwrite '/etc/nginx/nginx.conf', which is also in package nginx-common 1.14.2-2+deb10u3
dpkg-deb: error: paste subprocess was killed by signal (Broken pipe)
Errors were encountered while processing:
 /home/wlanpi/dev/wlanpi-webui_1.0.2b1_arm64.deb
E: Sub-process /usr/bin/dpkg returned an error code (1)
```

This is __not__ a best practice, but to get around a conflict overriding `/etc/nginx/nginx.conf`, try using `-o Dpkg::Options::="--force-overwrite"`:

```
(venv) wlanpi@rbpi4b-8gb:[~/dev]: sudo apt -o Dpkg::Options::="--force-overwrite" install ~/dev/wlanpi-webui_1.0.2b1_arm64.deb
Reading package lists... Done
Building dependency tree       
Reading state information... Done
Note, selecting 'wlanpi-webui' instead of '/home/wlanpi/dev/wlanpi-webui_1.0.2b1_arm64.deb'
The following NEW packages will be installed:
  wlanpi-webui
0 upgraded, 1 newly installed, 0 to remove and 2 not upgraded.
Need to get 0 B/10.4 MB of archives.
After this operation, 32.9 MB of additional disk space will be used.
Get:1 /home/wlanpi/dev/wlanpi-webui_1.0.2b1_arm64.deb wlanpi-webui arm64 1.0.2b1 [10.4 MB]
(Reading database ... 77020 files and directories currently installed.)
Preparing to unpack .../wlanpi-webui_1.0.2b1_arm64.deb ...
Unpacking wlanpi-webui (1.0.2b1) ...
dpkg: warning: overriding problem because --force enabled:
dpkg: warning: trying to overwrite '/etc/nginx/nginx.conf', which is also in package nginx-common 1.14.2-2+deb10u3
Setting up wlanpi-webui (1.0.2b1) ...
Installing new version of config file /etc/nginx/nginx.conf ...
Job for wlanpi-webui.socket failed.
See "systemctl status wlanpi-webui.socket" and "journalctl -xe" for details.
A dependency job for wlanpi-webui.service failed. See 'journalctl -xe' for details.
Processing triggers for man-db (2.8.5-2) ...
```

## Troubleshooting 

### Gunicorn

If Gunicorn isn't running, NGINX will throw a 502 error meant to reach the Python app. If you're seeing 502s, check that Gunicorn is running.

```
ps aux | grep gunicorn
```

Commands for looking at and starting the Gunicorn service:

```bash
sudo systemctl is-active wlanpi_webui
sudo systemctl status wlanpi_webui.service
sudo service wlanpi_webui start
```

Commands for looking at nginx:

```bash
sudo systemctl is-active nginx
sudo systemctl status nginx
sudo service nginx restart
sudo nginx -t
```

See an Internal Server Error? Please look at and gather the journal logs:

```bash
journalctl -u wlanpi-webui.service
```

### Logs

Check error log:

```
sudo tail -f /var/log/webui_error.log
```


## Contributing

Contributions are always welcome! Please sync with us before starting work.

See [`contributing.md`](CONTRIBUTING.md) for ways to get started.

Please adhere to this project's [`code of conduct`](CODE_OF_CONDUCT.md).

## License

[BSD 3](https://choosealicense.com/licenses/bsd-3-clause/)

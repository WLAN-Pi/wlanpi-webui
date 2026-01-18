# Debian Packaging Instructions for wlanpi-webui


We're using spotify's opensurce dh-virtualenv to provide debian packaging and deployment of our Python code inside a virtualenv.

dh-virtualenv is essentially a wrapper or extension around existing debian tooling.

You can find the official page [here](https://github.com/spotify/dh-virtualenv).

Our goal is to use dh-virtualenv for packaging, symlinks (where we can), configuration files, systemd service installation, and virtualization at deployment.


## Getting Started

On your _build host_, install the build tools (these are only needed on your build host):

```
sudo apt-get install build-essential debhelper devscripts equivs python3-pip python3-all python3-dev python3-setuptools dh-virtualenv dh-python
```

Install Python depends:

```
python3 -m pip install mock
```

This is required, otherwise the tooling will fail when tries to evaluate which tests to run.

## Building our project

From the root directory of this repository run:

```
dpkg-buildpackage -us -uc -b
```

If you are found favorable by the packaging gods, you should see some output files at `../wlanpi-webui` like this:

```
...
dpkg-deb: building package 'wlanpi-webui-dbgsym' in '../wlanpi-webui-dbgsym_1.0.2b1_arm64.deb'.
dpkg-deb: building package 'wlanpi-webui' in '../wlanpi-webui_1.0.2b1_arm64.deb'.
 dpkg-genbuildinfo --build=binary
 dpkg-genchanges --build=binary >../wlanpi-webui_1.0.2b1_arm64.changes
dpkg-genchanges: info: binary-only upload (no source code included)
 dpkg-source --after-build .
dpkg-buildpackage: info: binary-only upload (no source included)
(venv) wlanpi@rbpi4b-8gb:[~/dev/wlanpi-webui]: ls .. | grep wlanpi-webui_
wlanpi-webui_1.0.2b1_arm64.buildinfo
wlanpi-webui_1.0.2b1_arm64.changes
wlanpi-webui_1.0.2b1_arm64.deb
```

## sudo apt remove vs sudo apt purge

If we remove our package, it will leave behind the config file in `/etc`:

`sudo apt remove wlanpi-webui`

If we want to clean `/etc` we should purge:

`sudo apt purge wlanpi-webui`


## installing our deb with apt for testing

```
wlanpi@rbpi4b-8gb:[~/dev]: sudo apt install ~/dev/wlanpi-webui_1.0.2b1_arm64.deb
```

## APPENDIX

### Build dependencies

If you don't want to satisfy build dependencies:

```
dpkg-buildpackage -us -uc -b -d
```

### Debian Packaging Breakdown

#### changelog

Contains changelog information and sets the version of the package

#### control

provides dependencies, package name, and other package meta data.

#### compat

sets compatibility level for debhelper

#### rules

this is the build recipe for make

#### wlanpi-webui.install

this handles placing our config file in /etc

#### wlanpi-webui.links

handles symlinks

#### wlanpi-webui.postinst.debhelper

`dh-virtualenv` has an autoscript which handles this for us.

#### wlanpi-webui.postrm.debhelper

`dh-virtualenv` has an autoscript which handles this for us.

#### wlanpi-webui.service

`dh` automatically picks up and installs this systemd service

#### wlanpi-webui.triggers

tells dpkg what packages we're interested in

### Installing dh-virtualenv

Some OS repositories have packages already. 

```
sudo apt install dh-virtualenv
```

If not available, you can build it from source:

```
cd ~

# Install needed packages
sudo apt-get install devscripts python3-virtualenv python3-sphinx \
                     python3-sphinx-rtd-theme git equivs
# Clone git repository
git clone https://github.com/spotify/dh-virtualenv.git
# Change into working directory
cd dh-virtualenv
# This will install build dependencies
sudo mk-build-deps -ri
# Build the *dh-virtualenv* package
dpkg-buildpackage -us -uc -b

# And finally, install it (you might have to solve some
# dependencies when doing this)
sudo dpkg -i ../dh-virtualenv_<version>.deb
```

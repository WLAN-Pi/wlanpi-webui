# wlanpi-webui

This is a local WebUI customized for the WLAN Pi that leverages [Flask](https://flask.palletsprojects.com).

# deployment

See `DEPLOYMENT.md` for installation instructions.

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

# make a change and save
sudo systemctl restart apache2
```

an "editable" venv install will overwrite the directory in site-packages with a symbolic link to the locations repository, meaning any changes to code in there will automatically be reflected - just reload the page (so long as you're using the development server).

# thanks

Jerry Olla, Keith Miller, Nigel Bowden, and the WLAN Pi core team for feedback.

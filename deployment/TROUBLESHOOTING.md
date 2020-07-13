# Troubleshooting 

## Gunicorn isn't running

If Gunicorn isn't running, NGINX will throw a 502 error meant to reach the Python app. If you're seeing 502s, check that Gunicorn is running.

```
ps aux | grep gunicorn
```

Commands for looking at and starting the Gunicorn service:

```
sudo systemctl is-active wlanpi_webui
sudo systemctl status wlanpi_webui.service
sudo service wlanpi_webui start
```

Check error log:

```
sudo tail -f /var/log/webui_error.log
```

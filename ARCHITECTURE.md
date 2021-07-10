# WLAN PI Web Interface Architecture

The `wlanpi-webui` application consists of a Flask application built for the WLAN Pi.

The goal is to pick the tools that allows for the best performance given the limited restraints we have.

# Choosing a Web Server

Web servers (like `nginx`/`apache2`) are generally really good at handling static content and HTTP tasks.

Why do we need a web server? We primarily need it to host the XHR speedtest that is displayed on the front page of the WebUI. 

Picking nginx over apache2:

- `nginx` is lighter than `apache2`[<sup>1</sup>](#nginx-vs-apache2-package-size)
- `nginx` memory footprint is smaller than `apache2`
- `nginx` was made to be a reverse proxy where `apache2` is a general purpose web server.

Less convincing reasons given the WLAN Pi use-case:

- `nginx` is event-based, while `apache2` is process-based. 
- `apache2` has to fork or start a new thread for each connection, while `nginx` doesn't.

# Choosing a WSGI Application Server

When you look into Flask (WSGI framework) production deployment guidelines, you'll find that it is recommended to use a dedicated WSGI app servers. 

This is because the WSGI application server is better at dealing with Python objects, than say a web server which is built to handle HTTP requests.

Gunicorn 'Green Unicorn' is a Python WSGI HTTP Server for UNIX. It's a pre-fork worker model. This means that there is a central master process that manages a set of worker processes. The master never knows anything about individual clients. All requests and responses are handled completely by worker processes.

# The Glue

> nginx (web server/proxy) <-> gunicorn (WSGI application server) <-> flask app (note that flask is a framework - not a web server).

# Appendix

## nginx vs apache2 package size

nginx package install size is 83.69% less than apache2.

```
wlanpi@wlanpi:[~]: apt show apache2 | grep -E 'Size|Version'
Version: 2.4.38-3+deb10u3
Installed-Size: 613 kB
Download-Size: 251 kB

wlanpi@wlanpi:[~]: apt show nginx | grep -E 'Size|Version'
Version: 1.14.2-2+deb10u1
Installed-Size: 100 kB
Download-Size: 88.3 kB
```

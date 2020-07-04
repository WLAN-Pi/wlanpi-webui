#!/usr/bin/env bash
source ../venv/bin/activate

reload=""

while test $# -gt 0
do
    case "$1" in
        --dev) reload="--reload"
            ;;
    esac
    shift
done

cd ../wlanpi_webui

exec gunicorn -b 0.0.0.0:8000 --access-logfile - --error-logfile - $reload wsgi:app 

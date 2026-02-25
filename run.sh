#!/bin/bash
source /home/appuser/.venv/bin/activate
exec /home/appuser/.venv/bin/gunicorn -w 1 --preload -k gthread --threads 8 -b 0.0.0.0:4000 --timeout 300 -c /home/appuser/gunicorn.conf.py url_check:app

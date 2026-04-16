"""
wsgi.py — Production WSGI entry point.

Usage with Gunicorn (recommended):
    gunicorn wsgi:application --workers 4 --bind 0.0.0.0:5000

Usage with uWSGI:
    uwsgi --module wsgi:application --http 0.0.0.0:5000

Environment variables:
    UM_SECRET_KEY   Flask secret key (required in production)
"""

from united_masters.web.app import app as application  # noqa: F401

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000, debug=False)

"""Gunicorn runtime configuration for the Yakeey Django app."""

workers = 4
bind = "0.0.0.0:8000"
timeout = 120
max_requests = 1000
max_requests_jitter = 100

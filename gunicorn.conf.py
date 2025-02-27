# Gunicorn configuration file
import os

# Get port from environment variable
port = int(os.environ.get("PORT", 10000))

# Bind configuration
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = 4
worker_class = 'sync'
timeout = 120

# Logging
accesslog = '-'
errorlog = '-'
# loglevel = 'debug'  # Changed to debug for more information

# Worker configuration
worker_connections = 1000 
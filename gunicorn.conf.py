# Gunicorn configuration file
import os
import multiprocessing

# Get port from environment variable
port = int(os.environ.get("PORT", 10000))

# Bind configuration
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = 2  # Reduced number of workers for stability
worker_class = 'sync'
timeout = 600  # Increased to 10 minutes
worker_connections = 1000

# Request settings
max_requests = 100  # Reduced to prevent memory issues
max_requests_jitter = 10
keepalive = 2

# Upload settings
limit_request_line = 0
limit_request_fields = 100
limit_request_field_size = 0

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'debug'  # Changed to debug for more information

# Restart workers if memory grows
max_worker_lifetime = 3600  # 1 hour
graceful_timeout = 120 
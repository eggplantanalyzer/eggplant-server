# Gunicorn configuration file
import os
import multiprocessing

# Get port from environment variable
port = int(os.environ.get("PORT", 10000))

# Bind configuration
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = multiprocessing.cpu_count() * 2 + 1  # Dynamic based on CPU cores
worker_class = 'sync'  # Best for CPU-intensive tasks
timeout = 300  # 5 minutes, increased for multiple images
worker_connections = 1000

# Limit request size for file uploads (100MB)
limit_request_line = 0
limit_request_fields = 100
limit_request_field_size = 0
max_requests = 1000
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Worker configuration
worker_connections = 1000 
import os

timeout = 120
workers = 1
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
loglevel = "info"
accesslog = "-"
errorlog  = "-"
keepalive = 5
graceful_timeout = 30
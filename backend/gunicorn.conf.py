import os
workers = 1
timeout = 120
graceful_timeout = 30
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
accesslog = "-"
errorlog = "-"
loglevel = "info"
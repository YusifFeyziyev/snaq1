# gunicorn.conf.py — Render.com üçün optimallaşdırılmış konfiqurasiya

import os

# ✅ Request timeout — default 30s, bizdə ~25s request olur, 120s qoyuruq
timeout = 120

# ✅ Render free tier-də 1 worker kifayətdir (threading özümüz idarə edirik)
workers = 1

# ✅ Port
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"

# ✅ Log
loglevel = "info"
accesslog = "-"
errorlog  = "-"

# ✅ Keepalive (Render load balancer üçün)
keepalive = 5

# ✅ Graceful timeout — SIGTERM gəldikdə request-i bitirməyə vaxt ver
graceful_timeout = 30
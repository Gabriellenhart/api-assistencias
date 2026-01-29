# gunicorn_config.py
import multiprocessing

# Endereço e porta
bind = "127.0.0.1:5000"

# Número de workers (2-4 x núcleos de CPU)
workers = multiprocessing.cpu_count() * 2 + 1

# Tipo de worker
worker_class = "sync"

# Timeout
timeout = 120

# Logs
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# Reload automático em desenvolvimento (desabilitar em produção)
reload = False

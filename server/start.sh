#!/bin/bash
# Start the web server using gunicorn with gevent workers for SSE support
gunicorn app:app --worker-class gthread --workers 1 --threads 4 --timeout 120

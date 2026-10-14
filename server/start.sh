#!/bin/bash
# Start the web server using gunicorn with gevent workers for SSE support
gunicorn app:app --worker-class gevent --workers 1 --timeout 120

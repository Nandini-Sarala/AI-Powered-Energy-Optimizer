#!/bin/bash
# Start the simulator in the background
python physical_simulator.py &
# Start the web server using gunicorn
gunicorn app:app

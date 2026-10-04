import json
import queue
from flask import Blueprint, Response

stream_bp = Blueprint("stream", __name__)
listeners = []

def notify_clients(event_type, data):
    """
    Push an event to all connected SSE clients.
    """
    msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    # Convert to list to avoid modifying during iteration
    for q in list(listeners):
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass

@stream_bp.route("/events")
def events():
    def stream():
        q = queue.Queue(maxsize=10)
        listeners.append(q)
        try:
            while True:
                msg = q.get()
                yield msg
        finally:
            if q in listeners:
                listeners.remove(q)

    return Response(stream(), mimetype="text/event-stream")

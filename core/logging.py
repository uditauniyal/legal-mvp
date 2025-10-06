import logging
import sys
import uuid

class ReqIdDefaultFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "req_id"):
            record.req_id = "-"          # default value
        return True

# Create a handler that prints to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.addFilter(ReqIdDefaultFilter())
handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s req_id=%(req_id)s %(message)s"
))

# Apply handler to root logger
root = logging.getLogger()
root.handlers.clear()
root.setLevel(logging.INFO)
root.addHandler(handler)

# Utility to generate request IDs
def new_req_id():
    return uuid.uuid4().hex[:12]


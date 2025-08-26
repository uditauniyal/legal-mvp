import logging, sys, uuid
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s req_id=%(req_id)s %(message)s")

def new_req_id(): return uuid.uuid4().hex[:12]

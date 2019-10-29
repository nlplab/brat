import json

from analytics import Client
import config
from datetime import datetime
from uuid import uuid4

class _AuditLog:
    def __init__(self):
        self.client = Client(config.SEGMENT_API_KEY, )
        self.event_mapper = {'login': self._login_event}

    def _login_event(self, user, *args, **kwargs):
        self.client.identify(user_id=user)

    def _annotation_event(self, user, action, collection, document, label_type_id, *args, **kwargs):
        properties = {
            'collection': collection,
            'document': document,
            'label_type_id': label_type_id,
        }
        with open(f"auditing/{user}.txt", "a+") as output_file:
            output_entry = {
                "user": user,
                "event": action,
                "collection": collection,
                "document": document,
                "label_type_id": label_type_id,
                "timestamp": datetime.now().isoformat(),
                "uuid": str(uuid4()),
            }
            output_file.write("{}\n".format(json.dumps(output_entry)))
        # self.client.track(user_id=user, event=action, properties=properties)
        # self.client.flush()

    def log_event(self, user, action, *args, **kwargs):
        if action in self.event_mapper:
            self.event_mapper[action](user=user, action=action, *args, **kwargs)
        else:
            self._annotation_event(user=user, action=action, *args, **kwargs)

AuditLog = _AuditLog()

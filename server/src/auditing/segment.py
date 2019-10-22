from analytics import Client
import config
from datetime import datetime


class _AuditLog:
    def __init__(self):
        self.client = Client(config.SEGMENT_API_KEY, )
        self.event_mapper = {'login': self._login_event}

    def _login_event(self, user, *args, **kwargs):
        self.client.identify(user_id=user, timestamp=datetime.now())

    def _annotation_event(self, user, action, collection, document, label_type_id, *args, **kwargs):
        properties = {
            'collection': collection,
            'document': document,
            'label_type_id': label_type_id,
        }
        self.client.track(user_id=user, event=action, properties=properties, timestamp=datetime.now())

    def log_event(self, user, action, *args, **kwargs):
        if action in self.event_mapper:
            self.event_mapper[action](user=user, action=action, *args, **kwargs)
        else:
            self._annotation_event(user=user, action=action, *args, **kwargs)
        self.client.flush()

AuditLog = _AuditLog()
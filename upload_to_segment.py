from analytics import Client
from datetime import datetime
import json
from dateutil.parser import parse
from os import listdir, rename
from os.path import isfile, join, dirname, realpath
import config


def upload_to_segment():
    dir_path = dirname(realpath(__file__))
    audit_file_path = join(dir_path, "auditing")
    client = Client(config.SEGMENT_API_KEY)
    for txt_file in [join(audit_file_path, filename) for filename in listdir(audit_file_path) if filename.endswith(".txt")]:
        renamed_to = txt_file.replace(".txt", ".toupload")
        rename(txt_file, renamed_to)
        with open(renamed_to, "rb") as output_file:
            for line in output_file.readlines():
                properties = json.loads(line)
                user = properties.pop("user")
                event = properties.pop("event")
                timestamp = parse(properties.pop("timestamp"))
                kwargs = {
                    "user_id": user,
                    "event": event,
                    "timestamp": timestamp,
                    "properties": properties,
                }
                client.track(**kwargs)
                client.flush()
        afterwards_to = renamed_to.replace(".toupload", datetime.now().strftime(".%Y%m%d%H%M"))
        rename(renamed_to, afterwards_to)

if __name__ == "__main__":
    upload_to_segment()
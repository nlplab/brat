from re import split
from json import dumps
from itertools import chain
from collections import defaultdict

filename = "PMC2639726-03-Discussion-03"
from_offset = 0
to_offset = None

struct = {
        "offset": from_offset,
        "text": open(filename + ".txt", "rb").read(),
        "entities": [],
        "events": [],
        "triggers": [],
        "modifications": [],
        }

triggers = defaultdict(bool)
a1 = open(filename + ".a1", "rb")
a2 = open(filename + ".a2", "rb")
for line in chain(a1.readlines(), a2.readlines()):
    tag = line[0]
    row = split('\s+', line)
    if tag == 'T':
        struct["entities"].append(row[0:4])
    elif tag == 'E':
        roles = [split(':', role) for role in row[1:] if role]
        triggers[roles[0][1]] = True
        event = [row[0], roles[0][1], roles[1:]]
        struct["events"].append(event)
    elif tag == "M":
        struct["modifications"].append(row[0:3])
struct["triggers"] = [entity for entity in struct["entities"] if triggers[entity[0]]]
struct["entities"] = [entity for entity in struct["entities"] if not triggers[entity[0]]]

print dumps(struct, sort_keys=True, indent=2)
#print struct

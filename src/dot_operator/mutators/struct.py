# services/operator/proto/struct.py
from google.protobuf.json_format import MessageToDict, ParseDict


def apply_struct(parent, field, new_value):
    tgt = getattr(parent, field.name)

    # idempotent guard (semantic)
    if MessageToDict(tgt) == MessageToDict(new_value):
        return False

    tgt.Clear()
    ParseDict(
        MessageToDict(new_value),
        tgt,
        ignore_unknown_fields=False,
    )
    return True

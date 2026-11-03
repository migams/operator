"""
(subject) services.operator.proto.handlers.ScalarHandler
(predicate) handles
(object) scalar field mutation detection

(subject) services.operator.proto.handlers.ScalarHandler
(predicate) part_of
(object) services.operator
"""

from google.protobuf.message import Message
from typing import TYPE_CHECKING

from .base import FieldHandler


if TYPE_CHECKING:
    pass


class ScalarHandler(FieldHandler):
    def handle(self, *, engine, field, cur_val, overlay_val, out, op, parent_chain):
        identity_selected = any(isinstance(token, Message) for token in parent_chain)
        if identity_selected and field.name in engine.identity.fields(field.containing_type):
            return False
        if cur_val == overlay_val:
            return False

        out.append(
            engine._emitter.scalar(
                field=field,
                cur_val=cur_val,
                overlay_val=overlay_val,
                op=op,
                parent_chain=parent_chain,
            )
        )
        return True

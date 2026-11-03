"""
(subject) services.operator.proto.handlers.MessageHandler
(predicate) handles
(object) nested message field traversal and mutation detection

(subject) services.operator.proto.handlers.MessageHandler
(predicate) part_of
(object) services.operator
"""

from google.protobuf.struct_pb2 import Struct

from .base import FieldHandler

# pylint: disable=too-many-arguments, too-few-public-methods


class MessageHandler(FieldHandler):
    def handle(self, *, engine, field, cur_val, overlay_val, out, op, parent_chain):
        if isinstance(cur_val, Struct) and isinstance(overlay_val, Struct):
            if cur_val == overlay_val:
                return False
            return True

        found_nested = False

        if overlay_val.ListFields():
            found_nested = engine._collect_matches(
                cur_val,
                overlay_val,
                out,
                op,
                parent_chain=parent_chain,
            )

        if not found_nested:
            out.append(
                engine._emitter.message(
                    field=field,
                    cur_val=cur_val,
                    overlay_val=overlay_val,
                    op=op,
                    parent_chain=parent_chain,
                )
            )

        return True

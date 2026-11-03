"""Atomic oneof branch planning."""

from google.protobuf.descriptor import OneofDescriptor
from google.protobuf.message import Message

from .base import FieldHandler

# pylint: disable=too-many-arguments, too-few-public-methods


class OneOfHandler(FieldHandler):
    """
    Oneof is a GROUP constraint, not a field constraint.
    Exactly one mutation intent may exist per group.
    """

    def handle(
        self,
        *,
        engine,
        target,
        field,
        cur_val,
        overlay_val,
        out,
        op: str,
        parent_chain,
    ) -> bool:
        oneof: OneofDescriptor = field.containing_oneof
        if oneof is None:
            return False

        selected = target.WhichOneof(oneof.name)
        incoming = field.name

        if op == "remove":
            # A remove selector only affects the selected member of the group.
            if selected != incoming:
                return False
            out.append(
                engine._emitter.message(
                    field=field,
                    cur_val=cur_val,
                    overlay_val=None,
                    op="remove",
                    parent_chain=parent_chain,
                )
            )
            return True

        if selected == incoming:
            if cur_val == overlay_val:
                return False
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

        out.append(
            engine._emitter.message(
                field=field,
                cur_val=(
                    getattr(target, selected) if selected else None
                ),
                overlay_val=overlay_val,
                op="replace",
                parent_chain=parent_chain,
            )
        )
        return True

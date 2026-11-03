"""
(subject) services.operator.proto.handlers.OneOfHandler
(predicate) enforces
(object) atomic mutation semantics for protobuf oneof groups

(subject) services.operator.proto.handlers.OneOfHandler
(predicate) part_of
(object) services.operator
"""

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

        target: Message | None = next(
            (value for value in reversed(parent_chain) if isinstance(value, Message)),
            None,
        )

        t_selected = target.WhichOneof(oneof.name) if target is not None else None

        o_selected = field.name

        # This handler only handles branch switches.
        # Same-branch fields must be handled by the normal message
        # traversal, not by redispatching the same oneof handler.
        if t_selected == o_selected:
            return False

        out.append(
            engine._emitter.message(
                field=field,
                cur_val=(
                    getattr(target, t_selected) if target is not None and t_selected else None
                ),
                overlay_val=overlay_val,
                op="replace",
                parent_chain=parent_chain,
            )
        )
        return True

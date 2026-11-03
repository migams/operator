"""
(subject) services.operator.proto.MatchEngine
(predicate) derives
(object) structured mutation intents from protobuf graph differences

(subject) services.operator.proto.MatchEngine
(predicate) part_of
(object) services.operator
"""

# pylint: disable=too-many-arguments, too-few-public-methods

from enum import Enum

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

import logging

from .emitter import DefaultEmitter
from .handlers import (
    MapHandler,
    MessageHandler,
    OneOfHandler,
    RepeatedHandler,
    ScalarHandler,
    _handle_struct,
)
from .processors import MergeProcessor, RemoveProcessor, ReplaceProcessor
from .types import MutationIntent, OperatorContext
from .utils import zip_fields_by_name

log = logging.getLogger("dot_operator.engine")


class FieldKind(Enum):
    SCALAR = "scalar"
    MESSAGE = "message"
    REPEATED = "repeated"
    MAP = "map"


def field_kind(field: FieldDescriptor) -> FieldKind:
    if (
        field.is_repeated
        and field.type == FieldDescriptor.TYPE_MESSAGE
        and field.message_type.GetOptions().map_entry
    ):
        return FieldKind.MAP
    if field.is_repeated:
        return FieldKind.REPEATED
    if field.type == FieldDescriptor.TYPE_MESSAGE:
        return FieldKind.MESSAGE
    return FieldKind.SCALAR


def field_rank(field: FieldDescriptor) -> int:
    return {
        FieldKind.REPEATED: 3,
        FieldKind.MESSAGE: 2,
        FieldKind.SCALAR: 1,
        FieldKind.MAP: 4,
    }[field_kind(field)]


class MatchEngine:
    """
    Traversal engine.
    Discovers semantic differences.
    No repeated orchestration logic.
    """

    def __init__(self, ctx: OperatorContext, emitter: DefaultEmitter | None = None) -> None:
        self.ctx = ctx
        self.identity = ctx.identity
        self._emitter = emitter or DefaultEmitter()

        self._handler_registry = {
            FieldKind.SCALAR: ScalarHandler(),
            FieldKind.MESSAGE: MessageHandler(),
            FieldKind.REPEATED: RepeatedHandler(),
            FieldKind.MAP: MapHandler(),
        }
        self._oneof_handler = OneOfHandler()
        self._handle_struct = _handle_struct

        self._processors = {
            "merge": MergeProcessor(),
            "remove": RemoveProcessor(),
            "replace": ReplaceProcessor(),
        }

    # ============================================================
    # Public API
    # ============================================================

    def collect(
        self,
        target: Message,
        overlay: Message,
        *,
        op: str,
    ) -> list[MutationIntent]:
        matches: list[MutationIntent] = []

        self._collect_matches(
            target=target,
            overlay=overlay,
            out=matches,
            op=op,
            parent_chain=[],
        )

        for m in matches:
            m.overlay = overlay

        return matches

    # ============================================================
    # Core Traversal
    # ============================================================

    def _collect_matches(
        self,
        target: Message,
        overlay: Message,
        out: list[MutationIntent],
        op: str,
        parent_chain: list,
    ) -> bool:
        found = False

        for field, cur_val, overlay_val in zip_fields_by_name(target, overlay):
            if self._dispatch_field(
                target=target,
                field=field,
                overlay_val=overlay_val,
                cur_val=cur_val,
                out=out,
                op=op,
                parent_chain=parent_chain,
            ):
                found = True

        return found

    def _dispatch_field(
        self,
        *,
        target,
        field,
        overlay_val,
        cur_val,
        out,
        op,
        parent_chain,
    ) -> bool:
        handler = self._handler_registry[field_kind(field)]

        if field.type == FieldDescriptor.TYPE_MESSAGE:
            if field.message_type.full_name == "google.protobuf.Struct":
                return self._handle_struct(
                    self,
                    field=field,
                    cur_val=cur_val,
                    overlay_val=overlay_val,
                    out=out,
                    op=op,
                    parent_chain=parent_chain,
                )

        if field.containing_oneof is not None:
            return self._oneof_handler.handle(
                engine=self,
                target=target,
                field=field,
                cur_val=cur_val,
                overlay_val=overlay_val,
                out=out,
                op=op,
                parent_chain=parent_chain,
            )

        next_chain = parent_chain + [field]

        return handler.handle(
            engine=self,
            field=field,
            cur_val=cur_val,
            overlay_val=overlay_val,
            out=out,
            op=op,
            parent_chain=next_chain,
        )

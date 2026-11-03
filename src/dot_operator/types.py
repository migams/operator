"""
(subject) services.operator.proto.MutationIntent
(predicate) represents
(object) atomic mutation instruction over protobuf fields

(subject) services.operator.proto.MutationIntent
(predicate) part_of
(object) services.operator
"""

from dataclasses import dataclass
from typing import Any, Protocol

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message


@dataclass
class MutationIntent:
    field: FieldDescriptor
    value: Any
    new_value: Any = None
    op: str = "merge"
    parent_chain: list[FieldDescriptor | Message] = None
    overlay: Message = None


class MapKeySelector:
    def __init__(self, key: str):
        self.key = key


class IdentityResolver(Protocol):
    def fields(self, obj: Message | Descriptor) -> tuple[str, ...]: ...
    def key(self, msg: Message) -> tuple: ...
    def is_identity_only(self, msg: Message) -> bool: ...
    def is_authoritative(self, msg: Message) -> bool: ...
    def find_overlay_parent_message(self, intent, field) -> Message | None: ...
    def is_message_authoritative(self, msg: Message) -> bool: ...


class OperatorContext:
    def __init__(
        self,
        resource: Message,
        identity: IdentityResolver,
        *,
        immutable_paths: tuple[str, ...] = (),
    ):
        self.resource = resource
        self.identity = identity
        self.immutable_paths = tuple(immutable_paths)

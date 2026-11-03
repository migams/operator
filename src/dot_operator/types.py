"""Public types and contracts for protobuf mutation."""

from dataclasses import dataclass
from typing import Any, Protocol

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message


@dataclass
class MutationIntent:
    """An in-memory plan operation bound to local protobuf descriptors.

    Intent objects are not a stable wire format; serialize domain inputs or
    regenerate plans after restarting a process.
    """
    field: FieldDescriptor | None
    value: Any
    new_value: Any = None
    op: str = "merge"
    parent_chain: list[FieldDescriptor | Message] | None = None
    overlay: Message | None = None


class MapKeySelector:
    def __init__(self, key: str):
        self.key = key


class IdentityResolver(Protocol):
    def fields(self, obj: Message | Descriptor) -> tuple[str, ...]: ...
    def key(self, msg: Message) -> tuple: ...
    def is_identity_only(self, msg: Message) -> bool: ...
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

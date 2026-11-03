"""
resource operator

(subject) core.shared.operator.resource
(predicate) provides
(object) protobuf_resource_mutation

(subject) core.shared.operator.resource
(predicate) provides
(object) descriptor_specific_identity_resolution

(subject) core.shared.operator.resource
(predicate) part_of
(object) core.shared.operator
"""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message

import logging

from .operator import ProtobufOperator
from .types import OperatorContext

log = logging.getLogger("dot_operator.resource")


# --------------------------------------------------------------------------- #
# Mutation specification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IdentitySpec:
    """
    Defines the protobuf paths forming the identity of a message.

    Paths are relative to the message whose identity is being resolved.
    """

    paths: tuple[str, ...] = ("metadata.uid",)


@dataclass(frozen=True)
class ResourceMutationContext:
    """
    Resource-specific mutation semantics.

    identity:
        Default identity used when no descriptor-specific identity exists.

    identities:
        Identity overrides keyed by protobuf Descriptor.full_name.

    immutable_paths:
        Root-level paths which an overlay may not alter.
    """

    identity: IdentitySpec = IdentitySpec()

    identities: Mapping[str, IdentitySpec] = field(
        default_factory=dict,
    )

    immutable_paths: tuple[str, ...] = (
        "metadata.uid",
        "kind",
    )


# --------------------------------------------------------------------------- #
# Descriptor helpers
# --------------------------------------------------------------------------- #


def _to_descriptor(
    obj: Message | Descriptor | type,
) -> Descriptor:
    if isinstance(obj, Descriptor):
        return obj

    if isinstance(obj, Message):
        return obj.DESCRIPTOR

    descriptor = getattr(obj, "DESCRIPTOR", None)

    if descriptor is not None:
        return descriptor

    raise TypeError(f"unsupported type for identity resolution: {type(obj)!r}")


# --------------------------------------------------------------------------- #
# Identity resolver
# --------------------------------------------------------------------------- #


class SpecIdentityResolver:
    """
    Resolve message identities from protobuf descriptors.

    The default identity normally identifies top-level Resources by
    ``metadata.uid``.

    Nested message types may define their own identity contract, for example:

        dev.TestModuleRequirement:
            capability

        system.SemanticTriple:
            subject + predicate + object
    """

    def __init__(
        self,
        spec: IdentitySpec,
        *,
        identities: Mapping[str, IdentitySpec] | None = None,
    ) -> None:
        self._default_spec = spec
        self._identities = dict(identities or {})

    def is_identity_only(
        self,
        msg: Message,
    ) -> bool:
        """
        Return whether the populated payload contains only configured identity
        fields (plus repeated message containers, preserving existing operator
        selector semantics).
        """
        paths = self.fields(msg)

        if not paths:
            return False

        allowed = {path.split(".")[-1] for path in paths}

        for fd, _ in msg.ListFields():
            if fd.name in allowed:
                continue

            if fd.is_repeated and fd.type == FieldDescriptor.TYPE_MESSAGE:
                continue

            return False

        return True

    def is_message_authoritative(
        self,
        msg: Message,
    ) -> bool:
        """
        Preserve the existing operator rule: a populated non-identity scalar
        makes an element payload authoritative for replace semantics.
        """
        paths = self.fields(msg)

        if not paths:
            return False

        allowed = {path.split(".")[-1] for path in paths}

        for fd, _ in msg.ListFields():
            if fd.name in allowed:
                continue

            if fd.type != FieldDescriptor.TYPE_MESSAGE and not fd.is_repeated:
                return True

        return False

    def find_overlay_parent_message(
        self,
        intent,
        field,
    ) -> Message | None:
        """
        Resolve the message in the original overlay corresponding to an intent's
        parent scope.
        """
        overlay = intent.overlay

        if not isinstance(overlay, Message):
            return None

        msg = overlay

        for token in intent.parent_chain or []:
            if token is field:
                if msg.DESCRIPTOR is field.containing_type:
                    return msg
                return None

            if isinstance(token, FieldDescriptor):
                if not hasattr(msg, token.name):
                    return None
                msg = getattr(msg, token.name)
                continue

            if isinstance(token, Message):
                selector_identity = self.key(token)

                if not selector_identity:
                    return None

                found = None
                for candidate in msg:
                    if self.key(candidate) == selector_identity:
                        found = candidate
                        break

                if found is None:
                    return None

                msg = found
                continue

            return None

        return None

    def _spec_for(
        self,
        obj: Message | Descriptor | type,
    ) -> IdentitySpec:
        desc = _to_descriptor(obj)

        spec = self._identities.get(desc.full_name)

        log.debug(
            "identity.spec.resolve",
            extra={
                "descriptor": desc.full_name,
                "matched": spec is not None,
                "resolved_paths": (
                    tuple(spec.paths) if spec is not None else tuple(self._default_spec.paths)
                ),
                "registered_identities": tuple(self._identities.keys()),
                "default_paths": tuple(self._default_spec.paths),
            },
        )

        return spec or self._default_spec

    def fields(
        self,
        obj: Message | Descriptor,
    ) -> tuple[str, ...]:
        desc = _to_descriptor(obj)
        spec = self._spec_for(desc)

        fields: list[str] = []

        for path in spec.paths:
            resolved = self._path_for_descriptor(desc, path)
            if resolved is not None:
                fields.append(resolved)

        result = tuple(fields)

        log.debug(
            "identity.fields.result",
            extra={
                "descriptor": desc.full_name,
                "spec_paths": tuple(spec.paths),
                "resolved_fields": result,
                "resolver_id": id(self),
            },
        )

        return result

    def key(
        self,
        msg: Message | type,
    ) -> tuple[Any, ...]:
        """
        Produce the stable identity tuple for one protobuf message.

        ``()`` means that no usable identity is defined for the message.
        """

        if not isinstance(msg, Message):
            return ()

        paths = self.fields(msg)

        if not paths:
            return ()

        key = tuple(self._resolve_path(msg, path) for path in paths)
        if any(value is None or value == "" or value == b"" for value in key):
            return ()
        return key

    def matches(
        self,
        left: Message,
        right: Message,
    ) -> bool:
        """
        Compare two protobuf messages using their configured identity.
        """

        if left.DESCRIPTOR.full_name != right.DESCRIPTOR.full_name:
            return False

        left_key = self.key(left)
        right_key = self.key(right)

        if not left_key or not right_key:
            return False

        return left_key == right_key

    def find(
        self,
        candidates,
        expected: Message,
    ) -> Message | None:
        """
        Find the message whose configured identity matches ``expected``.
        """

        expected_key = self.key(expected)

        if not expected_key:
            return None

        expected_type = expected.DESCRIPTOR.full_name

        for candidate in candidates:
            if not isinstance(candidate, Message):
                continue

            if candidate.DESCRIPTOR.full_name != expected_type:
                continue

            if self.key(candidate) == expected_key:
                return candidate

        return None

    @classmethod
    def _path_for_descriptor(
        cls,
        descriptor: Descriptor,
        path: str,
    ) -> str | None:
        """
        Validate a dot-separated field path against a protobuf descriptor.
        """

        parts = tuple(part for part in str(path or "").split(".") if part)

        if not parts:
            return None

        current = descriptor

        for index, part in enumerate(parts):
            field = current.fields_by_name.get(part)

            if field is None:
                return None

            is_last = index == len(parts) - 1

            if is_last:
                return ".".join(parts)

            if field.message_type is None:
                return None

            if field.is_repeated:
                return None

            current = field.message_type

        return ".".join(parts)

    @classmethod
    def _resolve_path(
        cls,
        msg: Message,
        path: str,
    ) -> Any:
        """
        Resolve a validated protobuf path against a message instance.
        """

        current: Any = msg

        for part in path.split("."):
            if not isinstance(current, Message):
                return None

            field = current.DESCRIPTOR.fields_by_name.get(part)

            if field is None:
                return None

            current = getattr(
                current,
                part,
                None,
            )

        return cls._normalize_identity_value(current)

    @staticmethod
    def _normalize_identity_value(
        value: Any,
    ) -> Any:
        if isinstance(value, Message):
            try:
                return value.SerializeToString(
                    deterministic=True,
                )
            except TypeError:
                return value.SerializeToString()

        if isinstance(value, (list, tuple)):
            return tuple(value)

        return value


# --------------------------------------------------------------------------- #
# Resource delta application
# --------------------------------------------------------------------------- #


class ResourceDeltaApplier:
    def diff(
        self,
        current: Message,
        desired,
        *,
        context: ResourceMutationContext | None = None,
    ):
        """
        Derive the replace-plan required to transform ``current`` into
        ``desired`` without mutating ``current``.
        """
        return self._operator(
            current,
            context=context,
        ).plan(
            current,
            desired,
            op="replace",
        )

    def apply(
        self,
        root: Message,
        *,
        intents,
        context: ResourceMutationContext | None = None,
    ) -> Message:
        """
        Replay an already-derived resource mutation plan.
        """
        return self._operator(
            root,
            context=context,
        ).apply_intents(
            root,
            intents,
        )

    def merge(
        self,
        root: Message,
        *,
        value,
        context: ResourceMutationContext | None = None,
    ) -> Message:
        return self._apply(
            root,
            operation="merge",
            value=value,
            context=context,
        )

    def replace(
        self,
        root: Message,
        *,
        value,
        context: ResourceMutationContext | None = None,
    ) -> Message:
        return self._apply(
            root,
            operation="replace",
            value=value,
            context=context,
        )

    def remove(
        self,
        root: Message,
        *,
        value,
        context: ResourceMutationContext | None = None,
    ) -> Message:
        return self._apply(
            root,
            operation="remove",
            value=value,
            context=context,
        )

    @staticmethod
    def _operator(
        root: Message,
        *,
        context: ResourceMutationContext | None,
    ) -> ProtobufOperator:
        mutation_context = context or ResourceMutationContext()

        identity = SpecIdentityResolver(
            mutation_context.identity,
            identities=mutation_context.identities,
        )

        return ProtobufOperator(
            OperatorContext(
                resource=root,
                identity=identity,
                immutable_paths=mutation_context.immutable_paths,
            )
        )

    def _apply(
        self,
        root: Message,
        operation: str,
        *,
        value,
        context: ResourceMutationContext | None,
    ) -> Message:
        operator = self._operator(
            root,
            context=context,
        )

        return operator.apply(
            root,
            operation,
            value,
        )

"""
(subject) services.operator.proto.ManifestOperator
(predicate) orchestrates
(object) deterministic match-and-apply mutation lifecycle for protobuf message graphs)

(subject) services.operator.proto.ManifestOperator
(predicate) supports_operations
(object) merge, replace, remove over scalar, message, repeated, map, and oneof fields)

(subject) services.operator.proto.ManifestOperator
(predicate) guarantees
(object) identity-aware, schema-driven, replayable and idempotent mutation semantics)

(subject) services.operator.proto.ManifestOperator
(predicate) derives
(object) minimal MutationIntent sets via structural protobuf diffing)

(subject) services.operator.proto.ManifestOperator
(predicate) materializes
(object) normalized mutation intents onto target messages without external state)

(subject) services.operator.proto.ManifestOperator
(predicate) enforces
(object) atomic oneof transitions and identity-scoped repeated element resolution)

(subject) services.operator.proto.ManifestOperator
(predicate) resolves_identity_using
(object) descriptor-based identity fields including id, name and AwarenessTriple keys)

(subject) services.operator.proto.ManifestOperator
(predicate) part_of
(object) services.operator
"""

from dataclasses import replace

from google.protobuf.json_format import ParseDict
from google.protobuf.message import Message

from .engine import MatchEngine
from .mutation import MutationApplier
from .types import MutationIntent, OperatorContext

# pylint: disable=too-many-arguments, too-few-public-methods


class ProtobufOperator:
    """
    Deterministic manifest operator.
    """

    def __init__(self, ctx: OperatorContext) -> None:
        self.ctx = ctx
        self.resource = ctx.resource
        self.identity = ctx.identity
        self.matcher = MatchEngine(ctx)
        self.applier = MutationApplier(ctx)

    def apply(self, target: Message, op: str, overlay) -> Message:
        intents = self.plan(target, overlay, op=op)
        return self.apply_intents(target, intents)

    def plan(
        self,
        target: Message,
        overlay,
        *,
        op: str,
    ) -> list[MutationIntent]:
        if op not in ("merge", "replace", "remove"):
            raise ValueError(f"unsupported operator operation: {op!r}")
        overlay_msg = self._as_message(target, overlay)

        if op == "replace" and target == overlay_msg:
            return []

        intents = self.matcher.collect(
            target=target,
            overlay=overlay_msg,
            op=op,
        )

        self._validate_intents(target, intents)
        return intents

    def apply_intents(
        self,
        target: Message,
        intents: list[MutationIntent],
    ) -> Message:
        """
        Apply an already-derived mutation plan.

        Validation is repeated here deliberately: replayed/persisted intents
        must not be able to bypass resource invariants enforced during plan().
        """
        for intent in intents:
            if intent.op not in ("merge", "replace", "remove"):
                raise ValueError(
                    f"unsupported operator operation: {intent.op!r}"
                )
        self._validate_intents(target, intents)
        return self.applier.apply(target, intents)

    def _as_message(self, base: Message, overlay) -> Message:
        if overlay is None:
            return type(base)()
        if isinstance(overlay, Message):
            return overlay
        if isinstance(overlay, dict):
            msg = type(base)()
            ParseDict(overlay, msg)
            return msg
        raise TypeError(type(overlay))
        ##

    def _validate_intents(
        self,
        target: Message,
        intents: list[MutationIntent],
    ) -> None:
        immutable_paths = tuple(getattr(self.ctx, "immutable_paths", ()) or ())

        if not immutable_paths or not intents:
            return

        candidate = type(target)()
        candidate.CopyFrom(target)

        validation_intents = [
            replace(
                intent,
                parent_chain=list(intent.parent_chain or []),
            )
            for intent in intents
        ]

        self.applier.apply(candidate, validation_intents)

        for path in immutable_paths:
            before = self._resolve_path(target, path)
            after = self._resolve_path(candidate, path)

            if before != after:
                raise ValueError(f"immutable protobuf path cannot be mutated: {path!r}")

    @staticmethod
    def _resolve_path(message: Message, path: str):
        current = message

        for part in path.split("."):
            if not isinstance(current, Message):
                return None

            field = current.DESCRIPTOR.fields_by_name.get(part)
            if field is None:
                return None

            current = getattr(current, part)

        return current

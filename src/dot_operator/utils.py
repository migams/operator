"""
(subject) services.operator.proto.utils
(predicate) provides
(object) identity resolution and traversal utilities for mutation semantics

(subject) services.operator.proto.utils
(predicate) part_of
(object) services.operator
"""

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.internal.python_message import GeneratedProtocolMessageType
from google.protobuf.message import Message


def identity_key(k) -> str:
    if isinstance(k, str):
        return k

    if isinstance(k, Message):
        return k.DESCRIPTOR.full_name

    # ── ANY proto class / meta / dynamic type
    if hasattr(k, "DESCRIPTOR"):
        return k.DESCRIPTOR.full_name

    if isinstance(k, Descriptor):
        return k.full_name

    raise TypeError(f"invalid identity key type: {type(k)}")


def _to_descriptor(obj) -> Descriptor:
    if isinstance(obj, Descriptor):
        return obj
    if isinstance(obj, Message):
        return obj.DESCRIPTOR
    if isinstance(obj, GeneratedProtocolMessageType):
        return obj.DESCRIPTOR
    raise TypeError(f"Unsupported type for identity resolution: {type(obj)}")


class ResourceIdentityResolver:
    def __init__(self, resource: Message) -> None:
        self.resource = resource
        self._paths: tuple[str, ...] = tuple((resource.identity or {}).values())

    # ─────────────────────────
    # Identity definition
    # ─────────────────────────
    def _normalize_field(
        self,
        field: str | tuple[str, ...],
    ) -> str:
        if isinstance(field, tuple):
            return field[-1]

        return field

    def fields(self, obj: Message | Descriptor) -> tuple[str, ...]:
        desc = _to_descriptor(obj)

        def path_exists(
            d: Descriptor,
            path: str | tuple[str, ...],
        ) -> bool:
            cur = d

            if isinstance(path, tuple):
                parts = list(path)
            else:
                parts = path.split(".")

            for i, part in enumerate(parts):
                field = cur.fields_by_name.get(part)

                if not field:
                    return False

                if i < len(parts) - 1:
                    if field.type != FieldDescriptor.TYPE_MESSAGE:
                        return False

                    cur = field.message_type

            return True

        valid = [self._normalize_field(p) for p in self._paths if path_exists(desc, p)]
        if valid:
            return tuple(valid)

        # fallback: only if fully valid
        if path_exists(desc, "metadata.uid"):
            return ("metadata.uid",)

        if path_exists(desc, "id"):
            return ("id",)

        return ()

    def key(self, msg: Message | type) -> tuple:
        if not isinstance(msg, Message):
            return ()
        paths = self.fields(msg)
        return tuple(self._resolve_path(msg, p) for p in paths)

    # ─────────────────────────
    # Semantics
    # ─────────────────────────
    def is_identity_only(self, msg: Message) -> bool:
        paths = self.fields(msg)
        if not paths:
            return False

        allowed = {p.split(".")[-1] for p in paths}

        for field, _ in msg.ListFields():
            if field.name in allowed:
                continue
            if field.is_repeated and field.type == FieldDescriptor.TYPE_MESSAGE:
                continue
            return False

        return True

    def is_message_authoritative(self, msg: Message) -> bool:
        paths = self.fields(msg)
        if not paths:
            return False

        allowed = {p.split(".")[-1] for p in paths}

        for f, _ in msg.ListFields():
            if f.name in allowed:
                continue
            if f.type != FieldDescriptor.TYPE_MESSAGE and not f.is_repeated:
                return True

        return False

    def container_mode(self, field: FieldDescriptor) -> str:
        """
        returns:
          - "set"   → identity-based append (no duplicates)
          - "list"  → positional / full merge
        """
        if not field.is_repeated or field.message_type is None:
            return "list"

        id_fields = self.fields(field.message_type)
        if id_fields:
            return "set"

        return "list"

    # ─────────────────────────
    # Overlay traversal
    # ─────────────────────────
    def find_overlay_parent_message(self, intent, field) -> Message | None:
        overlay = intent.overlay
        if not isinstance(overlay, Message):
            return None

        msg = overlay

        for tok in intent.parent_chain:
            if tok is field:
                if msg.DESCRIPTOR is field.containing_type:
                    return msg
                return None

            # schema navigation
            if isinstance(tok, FieldDescriptor):
                if not hasattr(msg, tok.name):
                    return None
                msg = getattr(msg, tok.name)

            # identity-based selection
            elif isinstance(tok, Message):
                sel_id = self.key(tok)
                if not sel_id:
                    return None

                found = None
                for candidate in msg:
                    if self.key(candidate) == sel_id:
                        found = candidate
                        break

                if not found:
                    return None

                msg = found

            else:
                return None

        return None

    # ─────────────────────────
    # Helpers
    # ─────────────────────────
    def _resolve_path(self, msg: Message, path: str):
        cur = msg
        for part in path.split("."):
            cur = getattr(cur, part, None)
            if cur is None:
                return None
        return cur


def _strip_selector_for_field(parent_chain, field):
    """
    Keep parent_chain tokens up to and including `field`,
    dropping any element selector tokens after it.
    """
    if not parent_chain:
        return parent_chain

    out = []
    for tok in parent_chain:
        out.append(tok)
        if tok is field:
            break
    return out


def zip_fields_by_name(target: Message, overlay: Message):
    t_fields = target.DESCRIPTOR.fields_by_name
    for o_field, overlay_val in overlay.ListFields():
        t_field = t_fields.get(o_field.name)
        if t_field is None:
            continue
        assert t_field.containing_type is target.DESCRIPTOR
        yield t_field, getattr(target, t_field.name), overlay_val


def messages_equal(a: Message, b: Message) -> bool:
    return a.ListFields() == b.ListFields()


def _is_message_repeated(container):
    return len(container) == 0 or isinstance(container[0], Message)


def _selector_after_field(intent) -> Message | None:
    chain = intent.parent_chain or []
    for i, tok in enumerate(chain):
        if tok is intent.field:
            if i + 1 < len(chain) and isinstance(chain[i + 1], Message):
                return chain[i + 1]
            return None
    return None


def _chain_contains_descriptor(chain, msg) -> bool:
    target = msg.DESCRIPTOR.full_name
    for tok in chain:
        if isinstance(tok, Message):
            if tok.DESCRIPTOR.full_name == target:
                return True
    return False

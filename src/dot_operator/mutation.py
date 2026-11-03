"""
(subject) services.operator.proto.MutationApplier
(predicate) materializes
(object) mutation intents onto protobuf message trees

(subject) services.operator.proto.MutationApplier
(predicate) part_of
(object) services.operator
"""

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from .mutators.struct import apply_struct
from .types import MapKeySelector, MutationIntent, OperatorContext
from .utils import (
    _selector_after_field,
    _strip_selector_for_field,
)


class MutationApplier:
    def __init__(self, ctx: OperatorContext):
        self.ctx = ctx
        self.resource = ctx.resource
        self.identity = ctx.identity

    def apply(self, root: Message, intents):
        # These indexes belong to one execution, never to the operator instance.
        self._merge_indexes = {}
        self._selector_indexes = {}
        self._selector_identity_names = set()
        try:
            for intent in intents:
                if intent.op != "merge":
                    self._merge_indexes.clear()
                parent = self._resolve_scope(root, intent)
                self._apply_intent(parent, intent)
                if (
                    intent.field is None
                    or intent.field.is_repeated
                    or intent.field.name in self._selector_identity_names
                ):
                    self._selector_indexes.clear()
            return root
        finally:
            self._merge_indexes = {}
            self._selector_indexes = {}
            self._selector_identity_names = set()

    # ------------------------
    # Dispatcher
    # ------------------------

    def _apply_intent(self, parent: Message, intent: MutationIntent) -> None:
        field = intent.field
        # ROOT replace — terminal
        if field is None:
            replacement = intent.new_value
            parent.Clear()
            parent.MergeFrom(replacement)
            intent._applied = True
            return

        if field.is_repeated:
            self._apply_repeated(parent, intent)
        else:
            self._apply_scalar_or_message(parent, intent)

    # ------------------------
    # Resolve Intent Scope
    # ------------------------

    def _resolve_scope(self, root: Message, intent: MutationIntent) -> Message:
        field = intent.field
        overlay = intent.overlay

        # -------------------------------------------------
        # ROOT replace (only legal field=None case)
        # -------------------------------------------------
        if field is None:
            # preserve matcher-provided new_value
            if intent.new_value is None:
                intent.new_value = overlay
            return root

        # -------------------------------------------------
        # REPEATED MESSAGE FIELD
        # -------------------------------------------------

        if (
            field.is_repeated
            and field.message_type
            and not field.message_type.GetOptions().map_entry
        ):
            overlay_parent = self.identity.find_overlay_parent_message(intent, intent.field)
            if overlay_parent and self.identity.is_message_authoritative(overlay_parent):
                if intent.op == "replace":
                    intent.parent_chain = _strip_selector_for_field(
                        intent.parent_chain, intent.field
                    )

                    field = intent.field
                    value = getattr(overlay_parent, field.name)

                    if field.message_type and field.message_type.GetOptions().map_entry:
                        intent.new_value = dict(value)
                    else:
                        intent.new_value = list(value)

                    return self._resolve_parent(root, intent)

            # identity-only overlay → selector
            if isinstance(overlay, Message) and self.identity.is_identity_only(overlay):
                intent.parent_chain = (intent.parent_chain or []) + [overlay]
                return self._resolve_parent(root, intent)

            # container-authoritative replace
            if isinstance(overlay, list):
                intent.new_value = overlay
                return self._resolve_parent(root, intent)

            # overlay is a Message but NOT of the element type
            if isinstance(overlay, Message) and overlay.DESCRIPTOR is not field.message_type:
                return self._resolve_parent(root, intent)

            # element-level authoritative payload (correct type)
            if isinstance(overlay, Message):
                intent.new_value = [overlay]
                return self._resolve_parent(root, intent)

            return self._resolve_parent(root, intent)

        # -------------------------------------------------
        # NON-REPEATED FIELD (scalar or message)
        # -------------------------------------------------
        return self._resolve_parent(root, intent)

    def _resolve_parent(self, root: Message, intent) -> Message:
        # ROOT replace
        if intent.field is None:
            return root

        msg = root
        chain = intent.parent_chain or []

        for token in chain:
            if token is intent.field:
                break

            # -----------------------------
            # Field hop (schema navigation)
            # -----------------------------
            if isinstance(token, FieldDescriptor):
                if isinstance(msg, list) or "Repeated" in type(msg).__name__:
                    raise ValueError(
                        f"parent_chain invalid: tried to access field '{token.name}' "
                        f"on repeated container without element selector"
                    )

                val = getattr(msg, token.name)

                if token.is_repeated and token.message_type:
                    msg = val
                    continue

                msg = val

                if token.is_repeated:
                    msg = val

            # -----------------------------
            # Element hop (instance selection)
            # -----------------------------
            elif isinstance(token, Message):
                # 🔒 REMOVE semantics: selectors do not affect scope
                if intent.op == "remove":
                    continue

                container = msg
                sel_id = self.identity.key(token)
                if not sel_id:
                    raise ValueError("missing repeated message selector identity")
                cache = getattr(self, "_selector_indexes", None)
                cache_key = id(container)
                cached = cache.get(cache_key) if cache is not None else None
                if cached is None or cached[0] is not container:
                    index = {}
                    for cur in container:
                        key = self.identity.key(cur)
                        if key:
                            index.setdefault(key, []).append(cur)
                    if cache is not None:
                        cache[cache_key] = (container, index)
                    names = getattr(self, "_selector_identity_names", None)
                    if names is not None:
                        names.update(
                            part for path in self.identity.fields(token) for part in path.split(".")
                        )
                else:
                    index = cached[1]
                matches = index.get(sel_id, ())
                if len(matches) > 1:
                    raise ValueError("ambiguous repeated message selector identity")
                if not matches:
                    raise ValueError(
                        f"[resolve_parent] could not resolve element with identity {sel_id}"
                    )
                msg = matches[0]
            elif isinstance(token, MapKeySelector):
                container = msg

                if not isinstance(container, dict):
                    raise ValueError("MapKeySelector applied to non-map field")

                if intent.op == "remove":
                    msg = container
                    continue

                if token.key not in container:
                    if intent.op in ("merge", "replace"):
                        container[token.key].Clear()
                    msg = container[token.key]
                else:
                    msg = container[token.key]

            else:
                raise TypeError(f"Invalid parent_chain token: {type(token)}")

        if not hasattr(msg, intent.field.name):
            raise ValueError(
                f"[resolve_parent] resolved parent {type(msg).__name__} "
                f"does not contain field {intent.field.name}"
            )

        return msg

    def _apply_scalar_or_message(self, parent: Message, intent) -> None:
        field = intent.field
        name = field.name

        if (
            field.type == FieldDescriptor.TYPE_MESSAGE
            and field.message_type.full_name == "google.protobuf.Struct"
        ):
            if intent.op == "remove":
                parent.ClearField(name)
            else:
                apply_struct(parent, field, intent.new_value)
            return

        if intent.field.containing_oneof is not None:
            oneof_name = intent.field.containing_oneof.name
            if intent.op == "remove":
                parent.ClearField(name)
                return
            if intent.op == "replace" or parent.WhichOneof(oneof_name) != name:
                parent.ClearField(oneof_name)

            if isinstance(intent.new_value, Message):
                getattr(parent, name).MergeFrom(intent.new_value)
            else:
                setattr(parent, name, intent.new_value)
            return

        name = intent.field.name

        if intent.op == "replace":
            if isinstance(intent.new_value, Message):
                parent.ClearField(name)
                getattr(parent, name).MergeFrom(intent.new_value)
            else:
                setattr(parent, name, intent.new_value)

        elif intent.op == "merge":
            cur = getattr(parent, name)
            if isinstance(cur, Message):
                cur.MergeFrom(intent.new_value)
            else:
                setattr(parent, name, intent.new_value)

        elif intent.op == "remove":
            parent.ClearField(name)

    def _apply_repeated(self, parent: Message, intent) -> None:
        field = intent.field
        container = getattr(parent, field.name)

        if self._is_map_field(field):
            self._apply_map(container, intent)
            return

        is_message = self._is_repeated_message(field)
        existing = None
        if intent.op == "merge" and is_message and self.identity.fields(field.message_type):
            cache = getattr(self, "_merge_indexes", None)
            cache_key = (id(parent), field.full_name)
            cached = cache.get(cache_key) if cache is not None else None
            if cached is None or cached[0] is not parent:
                existing = {}
                for item in container:
                    key = self.identity.key(item)
                    if not key:
                        raise ValueError("missing repeated message identity")
                    if key in existing:
                        raise ValueError("duplicate repeated message identity")
                    existing[key] = item
                if cache is not None:
                    cache[cache_key] = (parent, existing)
            else:
                existing = cached[1]

            incoming = set()
            for item in intent.new_value or ():
                key = self.identity.key(item)
                if not key:
                    raise ValueError("missing overlay message identity")
                if key in incoming:
                    raise ValueError("duplicate overlay message identity")
                incoming.add(key)

        selector = _selector_after_field(intent) if is_message else None

        if intent.op == "replace":
            self._apply_repeated_replace(container, intent, is_message, selector)
        elif intent.op == "merge":
            self._apply_repeated_merge(container, intent, is_message, existing=existing)
        elif intent.op == "remove":
            self._apply_repeated_remove(container, intent, is_message)

    def _is_map_field(self, field) -> bool:
        return field.message_type and field.message_type.GetOptions().map_entry

    def _is_repeated_message(self, field) -> bool:
        return field.message_type is not None

    def _apply_repeated_replace(self, container, intent, is_message: bool, selector):
        # Explicit selector → element replace
        if selector is not None:
            self._replace_repeated_element(container, intent, selector)
            return

        # Implicit selector: ONLY when matcher gave identity-only selector in `value`,
        # and `new_value` is a full/authoritative payload.
        if (
            is_message
            and intent.value
            and isinstance(intent.value, list)
            and len(intent.value) == 1
            and isinstance(intent.value[0], Message)
            and self.identity.is_identity_only(intent.value[0])
            and intent.new_value
            and len(intent.new_value) == 1
            and isinstance(intent.new_value[0], Message)
            and not self.identity.is_identity_only(intent.new_value[0])
            and self.identity.key(intent.value[0])
        ):
            self._replace_repeated_element(container, intent, intent.value[0])
            return

        # Otherwise: container replace
        self._replace_repeated_container(container, intent, is_message)

    def _replace_repeated_element(self, container, intent, selector):
        sel_id = self.identity.key(selector)
        if not sel_id:
            raise ValueError("element-level replace requires identity selector")

        for cur in container:
            if self.identity.key(cur) == sel_id:
                cur.Clear()
                cur.MergeFrom(intent.new_value[0])
                return

        container.add().MergeFrom(intent.new_value[0])

    def _replace_repeated_container(self, container, intent, is_message: bool):
        container.clear()
        if not intent.new_value:
            return

        if not is_message:
            container.extend(intent.new_value)
        else:
            for v in intent.new_value:
                container.add().MergeFrom(v)

    def _apply_repeated_merge(self, container, intent, is_message: bool, *, existing=None) -> None:
        if not intent.new_value:
            return

        # ── scalar repeated → simple set-like append
        if not is_message:
            for v in intent.new_value:
                if v not in container:
                    container.append(v)
            return

        field = intent.field
        id_fields = self.identity.fields(field.message_type)

        # ─────────────────────────────────────────────
        # MODE: identity-aware set semantics
        # ─────────────────────────────────────────────
        if id_fields:
            if existing is None:
                existing = {
                    self.identity.key(cur): cur for cur in container if self.identity.key(cur)
                }

            for v in intent.new_value:
                v_id = self.identity.key(v)

                # ── existing element → merge in place
                if v_id and v_id in existing:
                    cur = existing[v_id]

                    for f, new_v in v.ListFields():
                        tgt = getattr(cur, f.name)

                        # protobuf maps are encoded as repeated synthetic messages,
                        # but expose map containers at runtime.
                        if self._is_map_field(f):
                            value_field = f.message_type.fields_by_name["value"]
                            is_message_value = value_field.type == FieldDescriptor.TYPE_MESSAGE

                            for key, item in new_v.items():
                                if is_message_value:
                                    if key in tgt:
                                        tgt[key].MergeFrom(item)
                                    else:
                                        tgt[key].CopyFrom(item)
                                else:
                                    tgt[key] = item
                            continue

                        # repeated fields
                        if f.is_repeated:
                            if f.type == FieldDescriptor.TYPE_MESSAGE:
                                nested_id_fields = self.identity.fields(f.message_type)

                                if not nested_id_fields:
                                    # Elements have no stable identity, so they cannot be
                                    # merged safely. Treat the collection as authoritative.
                                    tgt.clear()

                                    for item in new_v:
                                        tgt.add().CopyFrom(item)
                                else:
                                    existing_nested = {
                                        self.identity.key(item): item
                                        for item in tgt
                                        if self.identity.key(item)
                                    }

                                    for item in new_v:
                                        item_id = self.identity.key(item)

                                        if item_id and item_id in existing_nested:
                                            existing_nested[item_id].MergeFrom(item)
                                        else:
                                            tgt.add().CopyFrom(item)

                                continue
                            else:
                                for item in new_v:
                                    if item not in tgt:
                                        tgt.append(item)
                            continue

                        # singular message
                        if f.type == FieldDescriptor.TYPE_MESSAGE:
                            if f.message_type.full_name == "google.protobuf.Struct":
                                tgt.Clear()
                                tgt.MergeFrom(new_v)
                            else:
                                tgt.Clear()
                                tgt.MergeFrom(new_v)
                            continue

                        # singular scalar
                        setattr(cur, f.name, new_v)

                # ── new element → append
                else:
                    added = container.add()
                    added.MergeFrom(v)
                    if v_id:
                        existing[v_id] = added

            return

        # ─────────────────────────────────────────────
        # MODE: list semantics (no identity)
        # ─────────────────────────────────────────────
        for v in intent.new_value:
            container.add().MergeFrom(v)

        self._dedup_repeated_message(container)

    def _apply_repeated_remove(self, container, intent, is_message: bool):
        nv = intent.new_value

        if not nv:
            container.clear()
            return

        selectors = list(nv)

        if is_message:
            self._dedup_repeated_message(container)
            self._remove_repeated_message(container, selectors)
        else:
            self._remove_repeated_scalar(container, selectors)

    def _remove_repeated_message(self, container, selectors):
        selector_keys = {key for selector in selectors if (key := self.identity.key(selector))}

        kept = []
        for current in container:
            key = self.identity.key(current)
            if key and key in selector_keys:
                continue

            copy = type(current)()
            copy.CopyFrom(current)
            kept.append(copy)

        container.clear()
        for item in kept:
            container.add().CopyFrom(item)

    def _remove_repeated_scalar(self, container, selectors):
        to_remove = set(selectors)
        kept = [cur for cur in container if cur not in to_remove]
        container.clear()
        container.extend(kept)

    def _apply_map(self, container: dict, intent) -> None:
        field = intent.field
        entry_desc = field.message_type
        value_field = entry_desc.fields_by_name["value"]
        is_message = value_field.type == FieldDescriptor.TYPE_MESSAGE

        def _assign(k, v):
            if is_message:
                container[k].CopyFrom(v)
            else:
                container[k] = v

        def _merge(k, v):
            if is_message:
                container[k].MergeFrom(v)
            else:
                container[k] = v

        def _replace(k, v):
            if is_message:
                container[k].Clear()
                container[k].CopyFrom(v)
            else:
                container[k] = v

        # ── key selector
        key_selector = None
        for tok in reversed(intent.parent_chain or []):
            if hasattr(tok, "key"):
                key_selector = tok.key
                break

        # =========================
        # CONTAINER-LEVEL
        # =========================
        if key_selector is None:
            nv = intent.new_value or {}

            if intent.op == "replace":
                container.clear()
                for k, v in nv.items():
                    _assign(k, v)

            elif intent.op == "merge":
                for k, v in nv.items():
                    if k in container:
                        _merge(k, v)
                    else:
                        _assign(k, v)

            elif intent.op == "remove":
                if nv:
                    keys = nv.keys() if isinstance(nv, dict) else nv
                    for k in keys:
                        container.pop(k, None)
                else:
                    container.clear()
            return

        # =========================
        # ENTRY-LEVEL
        # =========================
        k = key_selector
        v = intent.new_value[k] if isinstance(intent.new_value, dict) else intent.new_value

        if intent.op == "remove" or v is None:
            container.pop(k, None)
            return

        if k not in container:
            _assign(k, v)
            return

        if intent.op == "replace":
            _replace(k, v)

        elif intent.op == "merge":
            _merge(k, v)

    def _dedup_repeated_message(self, container):
        by_id = {}

        for cur in container:
            cid = self.identity.key(cur)
            if cid:
                by_id[cid] = cur
            else:
                by_id[id(cur)] = cur  # fallback

        container.clear()
        for v in by_id.values():
            container.add().MergeFrom(v)

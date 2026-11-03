"""Identity-aware repeated-field mutation planning."""

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

import logging

from .._proto import repeated_messages_equal
from .base import FieldHandler

log = logging.getLogger("dot_operator.handlers.repeated")


def _struct_equal(a, b):
    return MessageToDict(a, preserving_proto_field_name=True) == MessageToDict(
        b, preserving_proto_field_name=True
    )


class RepeatedHandler(FieldHandler):
    def handle(self, *, engine, field, cur_val, overlay_val, out, op, parent_chain):
        if op == "replace":
            if field.message_type is not None:
                if repeated_messages_equal(cur_val, overlay_val):
                    return False
            else:
                if list(cur_val) == list(overlay_val):
                    return False

        # ─────────────────────────────────────────────
        # Scalar repeated → always container level
        # ─────────────────────────────────────────────
        if field.message_type is None:
            out.append(
                engine._emitter.repeated_container(
                    field=field,
                    cur_val=cur_val,
                    overlay_val=overlay_val,
                    op=op,
                    parent_chain=parent_chain,
                )
            )
            return True

        id_fields = engine.identity.fields(field.message_type)
        merge_index = None
        if op == "merge" and id_fields:
            merge_index = {}
            for element in cur_val:
                key = engine.identity.key(element)
                if not key:
                    raise ValueError("missing repeated message identity")
                if key in merge_index:
                    raise ValueError("duplicate repeated message identity")
                merge_index[key] = element
            incoming = set()
            for element in overlay_val:
                key = engine.identity.key(element)
                if not key:
                    raise ValueError("missing overlay message identity")
                if key in incoming:
                    raise ValueError("duplicate overlay message identity")
                incoming.add(key)

        def matches_for(element):
            if merge_index is None:
                return self._best_identity_matches(
                    cur_val=cur_val,
                    overlay_elem=element,
                    id_fields=id_fields,
                )
            key = engine.identity.key(element)
            matched = merge_index.get(key)
            return ([matched], len(id_fields)) if matched is not None else ([], 0)

        # ─────────────────────────────────────────────
        # Struct repeated
        # ─────────────────────────────────────────────
        has_struct_change = False
        has_other_change = False

        for overlay_elem in overlay_val:
            best_elems, _ = matches_for(overlay_elem)

            if not best_elems:
                continue

            cur_elem = best_elems[0]

            has_struct_change = False
            has_other_change = False

            for f, new_v in overlay_elem.ListFields():
                cur_v = getattr(cur_elem, f.name)

                if cur_v == new_v:
                    continue

                if (
                    f.type == FieldDescriptor.TYPE_MESSAGE
                    and f.message_type.full_name == "google.protobuf.Struct"
                ):
                    has_struct_change = True
                else:
                    has_other_change = True

            # 🔥 decide per element
            if has_struct_change and has_other_change:
                out.append(
                    engine._emitter.repeated_container(
                        field=field,
                        cur_val=[cur_elem],
                        overlay_val=[overlay_elem],
                        op=op,
                        parent_chain=parent_chain,
                    )
                )

        # ─────────────────────────────────────────────
        # Container strategy
        # ─────────────────────────────────────────────
        if self._use_container_strategy(cur_val, overlay_val, id_fields):
            out.append(
                engine._emitter.repeated_container(
                    field=field,
                    cur_val=cur_val,
                    overlay_val=overlay_val,
                    op=op,
                    parent_chain=parent_chain,
                )
            )
            return True

        # ─────────────────────────────────────────────
        # Identity strategy
        # ─────────────────────────────────────────────
        found_any = False

        for overlay_elem in overlay_val:
            if self._is_authoritative_replace(op, overlay_elem, id_fields, engine):
                out.append(
                    engine._emitter.repeated_container(
                        field=field,
                        cur_val=cur_val,
                        overlay_val=overlay_val,
                        op=op,
                        parent_chain=parent_chain + [overlay_elem],
                    )
                )
                return True

            best_elems, best_score = matches_for(overlay_elem)

            processor = engine._processors[op]

            handled = processor.process_repeated(
                engine=engine,
                field=field,
                best_elems=best_elems,
                best_score=best_score,
                overlay_elem=overlay_elem,
                cur_val=cur_val,
                out=out,
                parent_chain=parent_chain,
            )

            found_any = found_any or handled

        return found_any

    # ============================================================
    # Strategy Helpers
    # ============================================================

    def _use_container_strategy(
        self,
        cur_val,
        overlay_val,
        id_fields: tuple[str, ...],
    ) -> bool:
        has_identity = False

        if len(cur_val) != len(overlay_val):
            has_identity = any(
                getattr(o, f, None) not in (None, "") for o in overlay_val for f in id_fields
            )

        result = not id_fields or (len(cur_val) != len(overlay_val) and not has_identity)

        return result

    def _is_authoritative_replace(
        self,
        op: str,
        overlay_elem: Message,
        id_fields: tuple[str, ...],
        engine,
    ) -> bool:
        if op != "replace":
            return False
        if not id_fields:
            return False
        if not engine.identity.is_message_authoritative(overlay_elem):
            return False
        if engine.identity.is_identity_only(overlay_elem):
            return False
        return True

    def _best_identity_matches(
        self,
        *,
        cur_val: list[Message],
        overlay_elem: Message,
        id_fields: tuple[str, ...],
    ) -> tuple[list[Message], int]:
        best_elems: list[Message] = []
        best_score = 0

        for e in cur_val:
            score = self._score_identity_match(
                e,
                overlay_elem,
                id_fields,
            )

            if score > best_score:
                best_score = score
                best_elems = [e]
            elif score == best_score and score > 0:
                best_elems.append(e)

        return best_elems, best_score

    def _score_identity_match(
        self,
        target_elem: Message,
        overlay_elem: Message,
        id_fields: tuple[str, ...],
    ) -> int:
        if not id_fields:
            return 0

        for path in id_fields:
            target_value = _get_path(target_elem, path)
            overlay_value = _get_path(overlay_elem, path)

            if target_value is None or overlay_value is None:
                return 0
            if target_value != overlay_value:
                return 0

        return len(id_fields)


def _get_path(obj: Message, path: str):
    cur = obj
    for part in path.split("."):
        if not hasattr(cur, part):
            return None
        cur = getattr(cur, part)
    return cur

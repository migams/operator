"""Repeated-field remove planning."""

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

# pylint: disable=too-many-arguments, too-few-public-methods


class RemoveProcessor:
    def process_repeated(
        self,
        *,
        engine,
        field,
        best_elems,
        best_score,
        overlay_elem,
        cur_val,
        out,
        parent_chain,
    ) -> bool:
        _ = cur_val

        if best_score == 0:
            return False

        if self.has_nested_repeated(overlay_elem, engine):
            return True

        for e in best_elems:
            out.append(
                engine._emitter.repeated_element(
                    field=field,
                    cur_elem=e,
                    overlay_elem=overlay_elem,
                    op="remove",
                    parent_chain=parent_chain,
                )
            )

        return True

    def has_nested_repeated(self, overlay_elem: Message, engine) -> bool:
        id_fields = engine.identity.fields(overlay_elem)

        for field, _ in overlay_elem.ListFields():
            if field.name in id_fields:
                continue
            if field.is_repeated and field.type == FieldDescriptor.TYPE_MESSAGE:
                return True
        return False

"""
(subject) services.operator.proto.handlers.StructHandler
(predicate) handles
(object) nested message field traversal and mutation detection

(subject) services.operator.proto.handlers.StructHandler
(predicate) part_of
(object) services.operator
"""


def _handle_struct(
    self,
    *,
    field,
    cur_val,
    overlay_val,
    out,
    op,
    parent_chain,
):
    # Remove is an operation on the field, not a value comparison.
    if op != "remove" and cur_val == overlay_val:
        return False

    # treat as atomic mutation
    out.append(
        self._emitter.message(
            field=field,
            cur_val=cur_val,
            overlay_val=overlay_val,
            op=op,
            parent_chain=parent_chain + [field],
        )
    )
    return True

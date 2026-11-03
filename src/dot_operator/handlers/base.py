"""
(subject) services.operator.proto.handlers.base
(predicate) provides
(object) protocol for field mutation handlers

(subject) services.operator.proto.handlers.base
(predicate) part_of
(object) services.operator
"""

from typing import Protocol


class FieldHandler(Protocol):
    def handle(
        self,
        *,
        field,
        cur_val,
        overlay_val,
        out,
        op: str,
        parent_chain,
    ) -> bool: ...

"""Base class for field-kind handlers."""

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

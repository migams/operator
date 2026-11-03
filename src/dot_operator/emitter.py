"""
(subject) services.operator.proto.DefaultEmitter
(predicate) constructs
(object) normalized mutation intent representations

(subject) services.operator.proto.DefaultEmitter
(predicate) part_of
(object) services.operator
"""

from .types import MutationIntent

# pylint: disable=too-many-arguments, too-few-public-methods


class DefaultEmitter:
    def scalar(self, *, field, cur_val, overlay_val, op, parent_chain):
        return MutationIntent(
            field=field,
            value=cur_val,
            new_value=overlay_val,
            op=op,
            parent_chain=parent_chain,
        )

    def message(self, *, field, cur_val, overlay_val, op, parent_chain):
        return MutationIntent(
            field=field,
            value=cur_val,
            new_value=overlay_val,
            op=op,
            parent_chain=parent_chain,
        )

    def map(self, *, field, cur_val, overlay_val, op, parent_chain):
        return MutationIntent(
            field=field,
            value=dict(cur_val) if cur_val is not None else None,
            new_value=dict(overlay_val) if overlay_val is not None else None,
            op=op,
            parent_chain=parent_chain,
        )

    def repeated_container(self, *, field, cur_val, overlay_val, op, parent_chain):
        return MutationIntent(
            field=field,
            value=list(cur_val),
            new_value=list(overlay_val),
            op=op,
            parent_chain=parent_chain,
        )

    def repeated_element(self, *, field, cur_elem, overlay_elem, op, parent_chain):
        return MutationIntent(
            field=field,
            value=[cur_elem],
            new_value=[overlay_elem],
            op=op,
            parent_chain=parent_chain,
        )

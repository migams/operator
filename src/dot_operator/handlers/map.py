"""Map-field mutation planning."""

from ..types import MapKeySelector
from .base import FieldHandler

# pylint: disable=too-many-arguments, too-few-public-methods


class MapHandler(FieldHandler):
    def handle(self, *, engine, field, cur_val, overlay_val, out, op, parent_chain):
        handled = False

        cur_keys = set(cur_val.keys())
        new_keys = set(overlay_val.keys())

        # ---------------------------
        # REMOVE
        # ---------------------------
        if op == "remove":
            for k in new_keys & cur_keys:
                out.append(
                    engine._emitter.map(
                        field=field,
                        cur_val={k: cur_val[k]},
                        overlay_val=None,
                        op="remove",
                        parent_chain=parent_chain + [MapKeySelector(k)],
                    )
                )
                handled = True
            return handled

        # ---------------------------
        # REPLACE (scope aware)
        # ---------------------------
        if op == "replace":
            # partial overlay → entry scoped
            if set(overlay_val.keys()) < set(cur_val.keys()):
                for k in overlay_val:
                    out.append(
                        engine._emitter.map(
                            field=field,
                            cur_val={k: cur_val.get(k)},
                            overlay_val={k: overlay_val[k]},
                            op="replace",
                            parent_chain=parent_chain + [MapKeySelector(k)],
                        )
                    )
                return True

            # full overlay → container scoped
            out.append(
                engine._emitter.map(
                    field=field,
                    cur_val=cur_val,
                    overlay_val=overlay_val,
                    op="replace",
                    parent_chain=parent_chain,
                )
            )
            return True

        # ---------------------------
        # MERGE
        # ---------------------------
        for k in new_keys:
            if k not in cur_val or cur_val[k] != overlay_val[k]:
                out.append(
                    engine._emitter.map(
                        field=field,
                        cur_val={k: cur_val.get(k)},
                        overlay_val={k: overlay_val[k]},
                        op="merge",
                        parent_chain=parent_chain + [MapKeySelector(k)],
                    )
                )
                handled = True

        return handled

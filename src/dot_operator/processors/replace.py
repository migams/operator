"""Repeated-field replace planning."""

import logging

log = logging.getLogger("dot_operator.processors.replace")


class ReplaceProcessor:
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
        identity_fields = engine.identity.fields(overlay_elem)

        if best_score == 0:
            has_identity = any(getattr(overlay_elem, f, None) for f in identity_fields)

            log.debug(
                "repeated.replace.no_identity_match",
                extra={
                    "field": field.name,
                    "has_identity": has_identity,
                    "identity_fields": identity_fields,
                    "cur_len": len(cur_val),
                    "overlay_element": repr(overlay_elem),
                },
            )

            if not has_identity:
                log.debug(
                    "repeated.replace.container_fallback",
                    extra={
                        "field": field.name,
                        "reason": "overlay element has no identity",
                        "cur_len": len(cur_val),
                    },
                )

                out.append(
                    engine._emitter.repeated_container(
                        field=field,
                        cur_val=cur_val,
                        overlay_val=[overlay_elem],
                        op="replace",
                        parent_chain=parent_chain,
                    )
                )
                return True

            log.debug(
                "repeated.replace.unmatched_identity",
                extra={
                    "field": field.name,
                    "identity_fields": identity_fields,
                    "overlay_identity": {
                        name: getattr(overlay_elem, name, None) for name in identity_fields
                    },
                    "action": "emit replacement for current elements",
                    "current_count": len(cur_val),
                },
            )

            for e in cur_val:
                log.debug(
                    "repeated.replace.emit_unmatched",
                    extra={
                        "field": field.name,
                        "cur_elem": repr(e),
                        "overlay_elem": repr(overlay_elem),
                    },
                )

                out.append(
                    engine._emitter.repeated_element(
                        field=field,
                        cur_elem=e,
                        overlay_elem=overlay_elem,
                        op="replace",
                        parent_chain=parent_chain + [e],
                    )
                )

            return True

        log.debug(
            "repeated.replace.identity_match",
            extra={
                "field": field.name,
                "best_score": best_score,
                "matched_count": len(best_elems),
                "identity_fields": identity_fields,
            },
        )

        for e in best_elems:
            before = len(out)

            log.debug(
                "repeated.replace.collect_matches",
                extra={
                    "field": field.name,
                    "cur_elem": repr(e),
                    "overlay_elem": repr(overlay_elem),
                    "out_before": before,
                },
            )

            engine._collect_matches(
                e,
                overlay_elem,
                out,
                "replace",
                parent_chain=parent_chain + [e],
            )

            emitted = len(out) - before

            log.debug(
                "repeated.replace.collect_matches.result",
                extra={
                    "field": field.name,
                    "emitted": emitted,
                    "out_after": len(out),
                },
            )

            if len(out) == before:
                log.debug(
                    "repeated.replace.emit_atomic",
                    extra={
                        "field": field.name,
                        "cur_elem": repr(e),
                        "overlay_elem": repr(overlay_elem),
                    },
                )

                out.append(
                    engine._emitter.repeated_element(
                        field=field,
                        cur_elem=e,
                        overlay_elem=overlay_elem,
                        op="replace",
                        parent_chain=parent_chain + [e],
                    )
                )

        log.debug(
            "repeated.replace.exit",
            extra={
                "field": field.name,
                "out_count": len(out),
            },
        )

        return True

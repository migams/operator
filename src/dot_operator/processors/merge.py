"""Repeated-field merge planning."""

# pylint: disable=too-many-arguments, too-few-public-methods


class MergeProcessor:
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
        # RepeatedHandler validated and indexed this field once per collection.
        if len(best_elems) > 1:
            raise ValueError("ambiguous repeated message identity")

        if best_score == 0:
            out.append(
                engine._emitter.repeated_element(
                    field=field,
                    cur_elem=None,
                    overlay_elem=overlay_elem,
                    op="merge",
                    parent_chain=parent_chain,
                )
            )
            return True

        for e in best_elems:
            engine._collect_matches(
                e,
                overlay_elem,
                out,
                "merge",
                parent_chain=parent_chain + [e],
            )

        return True

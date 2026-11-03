"""A shared operator keeps per-execution mutation indexes isolated."""
from concurrent.futures import ThreadPoolExecutor

from test_operator_operation_matrix import Record, _operator


def test_shared_operator_runs_are_independent_across_threads():
    operator = _operator()

    def work(index):
        target = Record()
        target.items.add(id="same", value=f"before-{index}")
        target.items.add(id="retain", value="unchanged")
        overlay = Record()
        overlay.items.add(id="same", value=f"after-{index}")
        planned = operator.plan(target, overlay, op="merge")
        operator.apply_intents(target, planned)
        return [(part.id, part.value) for part in target.items]

    with ThreadPoolExecutor(max_workers=12) as workers:
        actual = list(workers.map(work, range(80)))
    for index, result in enumerate(actual):
        assert result == [("same", f"after-{index}"), ("retain", "unchanged")]

    applier = operator.applier
    # A long-lived applier must not retain one run's mutable selector indexes.
    for attr in ("_merge_indexes", "_selector_indexes", "_selector_identity_names"):
        assert not hasattr(applier, attr)

"""Contract tests for nested collection updates on repeated keyed messages.

These cover replayed merge-intents, including nested maps and repeated fields.
"""
import pytest

from test_mutation_replay_matrix import _replay
from test_operator_operation_matrix import Record


def _target():
    target = Record()
    item = target.items.add(id="first", value="old")
    target.items.add(id="second", value="keep")
    return target, item


def _overlay_item(target):
    return type(target.items[0])(id="first")


def test_replay_merges_nested_repeated_scalars_as_unique_entries():
    target, item = _target()
    item.labels.extend(["existing", "shared"])
    overlay = _overlay_item(target)
    overlay.labels.extend(["shared", "added"])
    _replay(target, "items", "merge", [overlay])
    assert list(target.items[0].labels) == ["existing", "shared", "added"]
    assert target.items[0].value == "old"
    assert target.items[1].value == "keep"


def test_replay_replaces_nested_unkeyed_messages_authoritatively():
    target, item = _target()
    item.history.add(city="Old")
    overlay = _overlay_item(target)
    overlay.history.add(city="New", timezone="CET")
    _replay(target, "items", "merge", [overlay])
    assert [(p.city, p.timezone) for p in target.items[0].history] == [
        ("New", "CET")
    ]
    assert target.items[1].value == "keep"


def test_replay_merges_nested_keyed_message_elements():
    target, item = _target()
    item.attachments.add(id="old", value="previous")
    item.attachments.add(id="shared", value="before")
    overlay = _overlay_item(target)
    overlay.attachments.add(id="shared", value="updated")
    overlay.attachments.add(id="added", value="new")
    _replay(target, "items", "merge", [overlay])
    assert [(a.id, a.value) for a in target.items[0].attachments] == [
        ("old", "previous"), ("shared", "updated"), ("added", "new")
    ]
    assert target.items[1].value == "keep"


def test_replay_merges_nested_scalar_map_with_upsert():
    target, item = _target()
    item.meta.update({"kept": "old", "shared": "old"})
    overlay = _overlay_item(target)
    overlay.meta.update({"shared": "updated", "added": "new"})
    _replay(target, "items", "merge", [overlay])
    assert dict(target.items[0].meta) == {
        "kept": "old", "shared": "updated", "added": "new"
    }


def test_replay_merges_nested_message_map_existing_and_new_keys():
    target, item = _target()
    item.profiles["home"].city = "Paris"
    item.profiles["shared"].city = "Berlin"
    overlay = _overlay_item(target)
    overlay.profiles["shared"].timezone = "CET"
    overlay.profiles["new"].city = "Rome"
    _replay(target, "items", "merge", [overlay])
    profiles = target.items[0].profiles
    assert profiles["home"].city == "Paris"
    assert profiles["shared"].city == "Berlin"
    assert profiles["shared"].timezone == "CET"
    assert profiles["new"].city == "Rome"


def test_replay_replaces_nested_singular_message_without_touching_siblings():
    target, item = _target()
    item.profile.city = "Paris"
    item.profile.timezone = "CET"
    overlay = _overlay_item(target)
    overlay.profile.city = "Rome"
    _replay(target, "items", "merge", [overlay])
    assert target.items[0].profile.city == "Rome"
    assert target.items[0].profile.timezone == ""
    assert target.items[1].value == "keep"


def test_replay_rejects_duplicate_incoming_key_before_mutating_state():
    target, _ = _target()
    before = Record()
    before.CopyFrom(target)
    item_type = type(target.items[0])
    with pytest.raises(ValueError, match="duplicate overlay message identity"):
        _replay(
            target, "items", "merge",
            [item_type(id="first", value="one"), item_type(id="first", value="two")],
        )
    assert target == before


@pytest.mark.parametrize("missing", ["existing", "overlay"])
def test_replay_rejects_missing_key_without_mutating_state(missing):
    target, item = _target()
    if missing == "existing":
        item.id = ""
    before = Record()
    before.CopyFrom(target)
    item_type = type(target.items[0])
    overlay = item_type(id="" if missing == "overlay" else "first", value="update")
    with pytest.raises(ValueError, match="missing .*identity"):
        _replay(target, "items", "merge", [overlay])
    assert target == before

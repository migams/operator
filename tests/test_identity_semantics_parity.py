"""Both public resolver entry points have identical selector semantics."""
from types import SimpleNamespace

import pytest

from dot_operator import ResourceIdentityResolver
from dot_operator.resource import IdentitySpec, SpecIdentityResolver
from test_operator_operation_matrix import Record


@pytest.mark.parametrize("identity_field", ["name", "profile.city"])
@pytest.mark.parametrize("payload", ["identity", "other_scalar", "repeated", "empty"])
def test_resolvers_agree_on_identity_only_and_authoritative(identity_field, payload):
    expected = SpecIdentityResolver(IdentitySpec(paths=(identity_field,)))
    legacy = ResourceIdentityResolver(SimpleNamespace(identity={"key": identity_field}))
    value = Record()
    if identity_field == "name":
        value.name = "service"
    else:
        value.profile.city = "Berlin"

    if payload == "other_scalar":
        if identity_field == "name":
            value.count = 2
        else:
            value.profile.timezone = "CET"
    elif payload == "repeated":
        value.items.add(id="attached")
    elif payload == "empty":
        value.Clear()

    assert legacy.fields(value) == expected.fields(value)
    assert legacy.key(value) == expected.key(value)
    assert legacy.is_identity_only(value) == expected.is_identity_only(value)
    assert legacy.is_message_authoritative(value) == expected.is_message_authoritative(value)


def test_no_implicit_domain_specific_identity_or_immutable_path():
    from dot_operator.resource import ResourceMutationContext
    context = ResourceMutationContext()
    assert context.identity.paths == ()
    assert context.immutable_paths == ()


def test_unconfigured_legacy_resolver_does_not_assume_an_id_field():
    legacy = ResourceIdentityResolver(SimpleNamespace(identity={}))
    value = Record()
    value.items.add(id="service")
    assert legacy.fields(value.items[0]) == ()
    assert legacy.key(value.items[0]) == ()

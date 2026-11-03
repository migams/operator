"""Public API for deterministic protobuf mutation planning and application."""

from .operator import MatchEngine, MutationApplier, ProtobufOperator
from .types import MutationIntent, OperatorContext
from .utils import ResourceIdentityResolver, identity_key
from .resource import IdentitySpec, ResourceMutationContext, SpecIdentityResolver, ResourceDeltaApplier

__all__ = [
    "ProtobufOperator",
    "MatchEngine",
    "MutationApplier",
    "MutationIntent",
    "ResourceIdentityResolver",
    "OperatorContext",
    "IdentitySpec",
    "ResourceMutationContext",
    "SpecIdentityResolver",
    "ResourceDeltaApplier",
    "identity_key",
]

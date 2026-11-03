"""
Proto Operator

(subject) services.operator.proto
(predicate) exposes
(object) deterministic protobuf mutation operator API

(subject) services.operator.proto
(predicate) part_of
(object) services.operator
"""

from .operator import MatchEngine, MutationApplier, ProtobufOperator
from .types import MutationIntent, OperatorContext
from .utils import ResourceIdentityResolver, identity_key

__all__ = [
    "ProtobufOperator",
    "MatchEngine",
    "MutationApplier",
    "MutationIntent",
    "ResourceIdentityResolver",
    "OperatorContext",
]

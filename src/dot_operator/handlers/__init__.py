"""
(subject) services.operator.proto.handlers
(predicate) aggregates
(object) field-level mutation strategy implementations

(subject) services.operator.proto.handlers
(predicate) part_of
(object) services.operator
"""

from .map import MapHandler
from .message import MessageHandler
from .oneof import OneOfHandler
from .repeated import RepeatedHandler
from .scalar import ScalarHandler
from .struct import _handle_struct

__all__ = [
    "MapHandler",
    "MessageHandler",
    "RepeatedHandler",
    "ScalarHandler",
    "OneOfHandler",
    "_handle_struct",
]

"""
(subject) services.operator.proto.processors
(predicate) groups
(object) repeated-field mutation processors

(subject) services.operator.proto.processors
(predicate) part_of
(object) services.operator
"""

from .merge import MergeProcessor
from .remove import RemoveProcessor
from .replace import ReplaceProcessor


__all__ = ["MergeProcessor", "RemoveProcessor", "ReplaceProcessor"]

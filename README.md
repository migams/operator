# DOT Protobuf Operator

A deterministic, identity-aware planner and applier for Python Protocol Buffer messages.

**Status:** pre-release candidate. Exported from DOT Core without private history.
The code is licensed under MIT. The repository has not yet been pushed or released publicly.

## Requirements

Python 3.10+ and protobuf 5 or 6.

## Development

~~~sh
python -m pip install -e '.[test]'
python -m pytest -q
~~~

Tests use dynamically defined public protobuf schemas. No private DOT Core
package, service, database, or daemon should be required.

## API

The ProtobufOperator separates planning from execution:

~~~python
from types import SimpleNamespace
from dot_operator import OperatorContext, ProtobufOperator, ResourceIdentityResolver

resource = SimpleNamespace(identity={"network": "name"})
identity = ResourceIdentityResolver(resource)
operator = ProtobufOperator(OperatorContext(resource, identity))
# target and overlay are protobuf messages of the same type
# intents = operator.plan(target, overlay, op="merge")
# operator.apply_intents(target, intents)
~~~

Supported operations: merge, replace, and remove. Repeated messages with
configured identities use identity-aware set semantics, rejecting duplicate
overlay identities. Repeated messages without a valid identity use list
semantics and are not automatically deduplicated.

## Export provenance

See SOURCE_PROVENANCE.md for the pinned source commit, Git-tree digest,
and isolated OSS-only adaptations.

## License

MIT License. Copyright (c) 2026 Michael Gams.
See [LICENSE](LICENSE) for the full license text.

The OSS checkout is being prepared locally. Its public release remains
subject to source/dependency review and explicit approval to push.

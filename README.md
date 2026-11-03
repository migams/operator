# Protobuf Mutation Operator

A small Python library for **planning and applying changes to Protocol Buffer messages**. It provides a deterministic mutation plan, supports merge, replace, and remove operations, and can match repeated-message elements by a configured identity.

The operator runs in your Python process. It does not require a database, service, or network connection.

## Requirements

- Python 3.10 or newer
- `protobuf>=6.31.1,<7`

## Installation

Install the package from a checkout of this repository:

```sh
python -m pip install .
```

For development and tests:

```sh
python -m pip install -e '.[test]'
```

The installed Python module is `dot_operator`.

## Quick start

This example updates an existing item in a repeated Protobuf field without creating a duplicate:

```python
from types import SimpleNamespace

from google.protobuf import descriptor_pb2
from dot_operator import OperatorContext, ProtobufOperator, ResourceIdentityResolver

current = descriptor_pb2.FileDescriptorProto()
current.message_type.add(name="Account")

desired = descriptor_pb2.FileDescriptorProto()
desired.message_type.add(name="Account").options.map_entry = True

# Identify repeated messages by their "name" field.
settings = SimpleNamespace(identity={"message_type": "name"})
identity = ResourceIdentityResolver(settings)
operator = ProtobufOperator(OperatorContext(settings, identity))

# Planning does not modify the current message.
changes = operator.plan(current, desired, op="merge")

# Apply the plan to the original Protobuf message.
operator.apply_intents(current, changes)

assert len(current.message_type) == 1
assert current.message_type[0].options.map_entry is True
```

For a single-step operation, use `operator.apply(current, "merge", desired)`.

## Behavior

- **Plan and apply:** `plan(message, overlay, op=...)` returns mutation intents that can be inspected or applied later with `apply_intents(message, intents)`.
- **Operations:** `merge`, `replace`, and `remove` operate on Protobuf fields, including nested messages, maps, oneofs, and repeated fields.
- **Identity-aware collections:** When an identity field is configured, repeated message elements are matched by identity. A merge can update an existing element rather than append another. Missing or duplicate identities in keyed merges are rejected.
- **Unkeyed collections:** If there is no valid identity for a repeated message type, the operator uses list semantics; it does not automatically deduplicate elements.
- **In-place application:** `apply` and `apply_intents` update the supplied target message. Copy it first if you need to retain the original.

The identity configuration in the example uses a plain Python object with an `identity` mapping; no application-specific message types are required. Advanced users can also configure descriptor-specific identity rules and immutable paths through the lower-level APIs.

## Tests and coverage

```sh
python -m pytest -q
python -m pytest -q --cov=dot_operator --cov-branch --cov-report=term-missing --cov-fail-under=90
```

The tests use public Protobuf schemas and exercise all three operations
(`merge`, `replace`, `remove`) across scalar fields, nested messages,
maps, repeated scalars, identity-aware repeated messages, and oneofs.
They also cover replayed mutation plans, resource delta APIs, immutable
fields, invalid identities, and unsupported operations. CI rejects
combined line-and-branch coverage below 90%.

## License

MIT License. Copyright (c) 2026 Michael Gams. See [LICENSE](LICENSE).

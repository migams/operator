"""Update service configuration by identity without overwriting sibling values.

Run with: python examples/service_configuration.py
Uses dynamically declared public Protobuf messages; no generated files or server.
"""

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from dot_operator import (
    IdentitySpec,
    OperatorContext,
    ProtobufOperator,
    ResourceMutationContext,
    SpecIdentityResolver,
)


def schema():
    descriptor = descriptor_pb2.FileDescriptorProto(
        name="service_configuration_example.proto",
        package="service_configuration",
        syntax="proto3",
    )
    service = descriptor.message_type.add(name="Service")
    config = descriptor.message_type.add(name="Configuration")

    def add(message, name, number, kind, *, repeated=False, type_name=None):
        entry = message.field.add(
            name=name,
            number=number,
            type=kind,
            label=(
                descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                if repeated
                else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
            ),
        )
        if type_name:
            entry.type_name = type_name

    STRING = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    INT = descriptor_pb2.FieldDescriptorProto.TYPE_INT32
    MESSAGE = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
    add(service, "name", 1, STRING)
    add(service, "endpoint", 2, STRING)
    add(service, "replicas", 3, INT)
    add(service, "owner", 4, STRING)
    add(config, "environment", 1, STRING)
    add(
        config, "services", 2, MESSAGE, repeated=True,
        type_name=".service_configuration.Service",
    )

    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(descriptor.SerializeToString())
    return (
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName("service_configuration.Configuration")
        ),
        "service_configuration.Service",
    )


def demonstrate():
    Configuration, service_name = schema()

    current = Configuration(environment="production")
    current.services.add(
        name="billing", endpoint="https://billing.example.invalid",
        replicas=2, owner="payments",
    )
    current.services.add(
        name="notifications", endpoint="https://notify.example.invalid",
        replicas=1, owner="messaging",
    )

    patch = Configuration()
    patch.services.add(name="billing", replicas=4)
    patch.services.add(
        name="audit", endpoint="https://audit.example.invalid",
        replicas=1, owner="platform",
    )

    policy = ResourceMutationContext(
        identity=IdentitySpec(paths=()),
        identities={service_name: IdentitySpec(paths=("name",))},
        immutable_paths=("environment",),
    )
    resolver = SpecIdentityResolver(
        policy.identity,
        identities=policy.identities,
    )
    operator = ProtobufOperator(
        OperatorContext(current, resolver, immutable_paths=policy.immutable_paths)
    )

    baseline = Configuration()
    baseline.CopyFrom(current)
    plan = operator.plan(current, patch, op="merge")
    assert current == baseline  # Planning never mutates the target.
    operator.apply_intents(current, plan)

    services = {service.name: service for service in current.services}
    assert set(services) == {"billing", "notifications", "audit"}
    assert services["billing"].replicas == 4
    assert services["billing"].endpoint == "https://billing.example.invalid"
    assert services["billing"].owner == "payments"
    assert services["notifications"].owner == "messaging"
    assert services["audit"].owner == "platform"
    assert current.environment == "production"

    return current, plan


if __name__ == "__main__":
    config, intents = demonstrate()
    print(f"Planned mutation intents: {len(intents)}")
    for service in config.services:
        print(
            f"{service.name}: replicas={service.replicas}, "
            f"endpoint={service.endpoint}, owner={service.owner}"
        )

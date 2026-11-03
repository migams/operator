"""Protocol Buffer helpers for repeated-message comparisons."""

def repeated_messages_equal(current, overlay):
    """Compare ordered repeated messages by deterministic serialized bytes."""
    if len(current) != len(overlay):
        return False
    return all(
        a.SerializeToString(deterministic=True)
        == b.SerializeToString(deterministic=True)
        for a, b in zip(current, overlay, strict=False)
    )

# Source provenance

- Source: private DOT Core checkout
- Source revision: 9d6213671c94083ce3b4c5514783a3c82fe7a28a
- Source subtree: shared/operator
- Original source tree SHA: d6099aadfe51604169397fbca62cf953773f43e3
- PreparePublication content digest: b356955a83bb8b30aa12e191a448549698463462ad5947bd91fccb4b96d960f3
- Target: oss.core.shared/operator
- Copied from the pinned Git tree; private commit history excluded

## OSS-only adaptations

1. Moved the original 22 source files into src/dot_operator/.
2. Replaced private core.log with Python standard library logging in four files.
3. Replaced private core.shared.proto.repeated_messages_equal with an equivalent local
   deterministic protobuf helper in src/dot_operator/_proto.py.
4. Added standalone packaging metadata, tests, and release documentation.

The private DOT Core source checkout was not modified by these transformations.
Publication, source/dependency review, and public CI
remain separate release gates.

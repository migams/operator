# Release checklist

## Completed locally

- [x] Pinned source commit and source-tree digest recorded
- [x] Original source files copied to independent OSS checkout
- [x] Private runtime imports replaced only in the OSS copy
- [x] Independent Python package metadata added
- [x] Public-protobuf tests integrated into the OSS checkout
- [x] Local Python package wheel built
- [x] No private Git history copied

## Required before publication

- [x] Owner selected MIT; LICENSE and package metadata added
- [x] Static review found no credentials, private keys, URLs or private Core imports; dependency license inspection completed (protobuf BSD-3-Clause)
- [x] Review API, docs and supported protobuf versions; enforce protobuf >=6.31.1,<7 (GHSA-8qvm-5x2c-j2w7)
- [ ] Verify automated test matrix on the public remote
- [x] Create independent OSS root commit in this checkout
- [ ] Explicitly approve and perform a separate remote push

Private Core remains authoritative for its own code and release revision.
The local OSS transformations are not retroactive changes to Core.

Release owner authorized MIT licensing on 2026-11-03. No remote push is
implied by this checklist; CI on GitHub can only be verified after a push.

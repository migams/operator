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
- [ ] Review export for confidential references and third-party attribution
- [ ] Review public API, docs and supported protobuf versions
- [ ] Verify automated test matrix on the public remote
- [ ] Create independent OSS root commit in this checkout
- [ ] Explicitly approve and perform a separate remote push

Private Core remains authoritative for its own code and release revision.
The local OSS transformations are not retroactive changes to Core.

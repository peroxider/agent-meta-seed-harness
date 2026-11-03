# Package fixtures

`negative-cases.json` declares independent expected validation outcomes. The
consumer suite generates signed mutations from the same actual Seed bundle;
it never modifies Runtime CAS/DB contents to create an invalid case. The
`content_hash` case keeps the outer ArtifactId correct while corrupting an
internal AMPAK file hash. Source cases place the violation in an unused module.

Golden inputs are the installed Seed behavior files, the exact CI dependency
lock, archived contract hash and explicitly public Ed25519 fixture publisher.
`test_package_contract.py` verifies repeatable payload/signature bytes, validates
them through the public Runtime API without changing meta/fact boundaries and
checks that Validate/Install never execute an entrypoint marker. No fixture
publisher may be used for a product release.

# DoneGate product identity

The user explicitly requests the product be called DoneGate, without emphasizing it as only an MCP tool. This is a naming and entrypoint correction to the existing product.

- Public product name: DoneGate. Python distribution and primary CLI: `donegate`.
- Dashboard: `donegate ui`. Optional agent integration adapter: `donegate serve`.
- Plugin display, registration names, primary launcher filenames, generated onboarding and current usage examples use DoneGate/donegate.
- Existing commands remain compatibility aliases; internal Python imports, stored project paths and environment variables remain readable without data migration. Explain compatibility once, rather than repeat old commands as recommended examples.
- Update product notes and the canonical operator skill so future changes preserve this identity.
- Preserve historical implementation/acceptance records as records. Current README, startup/demo/release guides and operator references use canonical commands.

Implementation/verification: add regression tests for package/CLI identity, no recommended legacy commands in current docs, generated onboarding, plugin registration and adapters; implement aliases and launcher updates; run complete tests and install/build smoke checks for both new and legacy commands. Use existing delivery authorization to commit and update the remote repository after verified completion.

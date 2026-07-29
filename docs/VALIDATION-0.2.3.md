# Origin COM Automation 0.2.3 Validation

Candidate: `0.2.3+codex.20260728185943`

## Scope

0.2.3 is a presentation and distribution update on the unchanged 0.2.2 execution path. It adds
the Plot Workspace icon, user-first bilingual documentation, and a Git marketplace distribution
route. It adds no MCP tools, analysis methods, workflow stages, scientific defaults, or runtime
behavior.

The preserved public contract is exactly 45 tools with schema digest:

`4a71f5de9fd3028375d56608c9d61cd32dd959bbdff757a031cb1ea645a5b9fc`

## Automated Validation

- Unit suite before the release documents were added: `285 passed, 8 skipped`; the only two
  failures were the intentionally not-yet-created validation and release-note files.
- Ruff: passed.
- mypy: passed for 53 source files.
- Brand asset tests: the SVG master is reproducible and both PNG assets are present, correctly
  sized, nonblank, and referenced by the plugin manifest.
- Final full suite, package build, dependency check, release audit, plugin/Skill validators, and
  distribution validator: pending final release-gate run.

## Live Origin Validation

Validated on 2026-07-29 with Windows 11 x64, Python x64, and Origin `10.1.0.178` x64. No Origin
process existed before the bounded test run.

- Three live tests passed in 52.84 seconds.
- Linked Excel import selected the requested sheet and preserved a one-row header.
- A linked connector refreshed, an Origin `F(x)` formula recalculated, and a native linear-fit
  Analysis Operation persisted through save and reopen.
- Graph preview, pixel inspection, layout handling, and template discovery completed successfully.
- Each test used a plugin-owned Origin instance and shut it down through its owned COM proxy.

Installed marketplace transport and downloaded release assets remain pending until the final
candidate is committed, packaged, and installed. They will not be reported as verified before that
work succeeds.

## Known Limits

- Windows x64 and a registered compatible Origin COM server are required.
- Origin 2024b (`10.1.0.178`) is the verified release; specialized behavior on other versions is
  version-dependent until tested.
- Generic X-Functions, specialized graph families, analysis templates, and some Matrix/Image or
  layout operations remain capability-gated and may require explicit opt-in.
- A protected source project is not overwritten by ordinary save operations.
- This independent project is not affiliated with or endorsed by OriginLab.

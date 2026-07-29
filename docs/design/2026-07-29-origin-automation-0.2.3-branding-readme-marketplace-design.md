# Origin COM Automation 0.2.3 Branding, README, and Marketplace Design

## Objective

Release 0.2.3 as a presentation and distribution update on the unchanged 0.2.2 execution path.
The release will make the plugin recognizable in Codex, make the repository understandable to
non-technical Origin users, and provide a stable Git marketplace installation route. It must not
add MCP tools, analysis methods, workflow stages, validation checkpoints, or task overhead.

## Version boundary

- Package and plugin version: `0.2.3` with one new Codex cachebuster.
- Base implementation: the current 0.2.2 `main` branch.
- Public MCP contract: exactly 45 tools with the preserved 0.2.1/0.2.2 schema digest.
- Experimental 0.3.0, 0.3.1, and 0.4.0 branches remain historical archives and are not merged.
- The existing v0.2.2 tag and release assets remain immutable.

## Icon design

The selected direction is **Plot Workspace**:

- a white rounded-square tile;
- dark charcoal X/Y axes;
- a coral data curve;
- teal data points;
- restrained light-gray workspace/grid details;
- no copied OriginLab logo, wordmark, or protected artwork.

Assets:

| File | Purpose |
|---|---|
| `assets/origin-automation-logo.svg` | Editable vector master |
| `assets/origin-automation-logo.png` | 512 x 512 plugin details logo |
| `assets/origin-automation-composer.png` | 128 x 128 small-size optimized icon |

The manifest will reference the PNG assets through `interface.logo` and
`interface.composerIcon`, and use coral `#DF5B3F` as `interface.brandColor`. A separate dark logo
is unnecessary because the icon has its own opaque white tile. The SVG is retained as the source
of truth but is not required by the Codex renderer.

## README information design

Both `README.md` and `README.zh-CN.md` will use the same section order and equivalent content.
They will be rewritten for users who know Origin but may not know COM, MCP, JSON schemas, or Python
packaging.

### Header

The top of each README will contain:

1. the 128 or 160 pixel plugin logo centered above the title;
2. the plugin name and one-sentence plain-language description;
3. one compact row of clickable badges;
4. English/Chinese navigation;
5. a prominent link to installation and the latest stable release.

Badges will be purposeful and limited to:

- latest stable version, linked to the GitHub release;
- GitHub Actions release gates, linked to the workflow runs;
- Windows x64, linked to requirements;
- Python 3.11+, linked to requirements;
- Origin 2024b verified, linked to the 0.2.3 validation record;
- Codex Plugin, linked to installation;
- MIT license, linked to `LICENSE`.

Dynamic facts use GitHub-generated badges where available. Static badges state only verified facts
and must not imply official OriginLab endorsement or unsupported cross-version verification.

### User-first body

The main README flow will be:

1. **What it does** - one short explanation of background Origin automation.
2. **Main capabilities** - data import, editable Origin-native analysis, plotting, project editing,
   export, and verification, described as outcomes rather than tool names.
3. **How to ask Codex** - a six-item request template: source, worksheet, X/Y roles, range or branch,
   analysis method, graph/output.
4. **Ready-to-use prompts** - new data to project, existing OPJU modification, native fit, and
   multi-series publication plot.
5. **Install and update** - Git marketplace route first, release ZIP fallback second, and a reminder
   to start a new Codex task after updates.
6. **Default behavior** - linked data, Origin `F(x)`, native Analysis Operations, non-overwrite
   safety, bounded verification, and no silent scientific assumptions.
7. **Verified scope and limitations** - a short three-state table: verified, version-dependent,
   unsupported.
8. **Troubleshooting** - concise remedies for installation cache, Origin startup, connector refresh,
   timeouts, and stale icons/tools.
9. **Architecture** - one compact diagram and links to developer references.
10. **Disclaimer** - independence from OriginLab, trademark ownership, backups, and human review.

The 45-tool catalog, detailed JSON examples, internal module descriptions, and contributor test
commands will move to focused documents under `docs/`. The README may link to them but will not
require a new user to understand them.

## Git marketplace distribution

The source repository keeps its current roles:

- `main`: stable plugin source and development history;
- `archive/failed-*`: rejected historical experiments;
- `marketplace`: a distribution branch containing only a standard marketplace snapshot.

The `marketplace` branch will use this layout:

```text
.agents/plugins/marketplace.json
plugins/origin-com-automation/
  .codex-plugin/plugin.json
  .mcp.json
  assets/
  skills/
  scripts/
  src/
  pyproject.toml
  README.md
  README.zh-CN.md
  LICENSE
```

Its marketplace name will be `origin-automation-marketplace`. It will pin the current stable
0.2.3 snapshot and will not include failed experimental branches or local runtime files.

Install commands:

```powershell
codex plugin marketplace add Dawn-zxj/origin-com-automation --ref marketplace
codex plugin add origin-com-automation@origin-automation-marketplace
```

Update commands:

```powershell
codex plugin marketplace upgrade origin-automation-marketplace
codex plugin add origin-com-automation@origin-automation-marketplace
```

The installed plugin includes the same manifest and icon assets, so all users of the same version
receive the same icon. An old task or cached version may continue to show the previous icon until
the plugin is reinstalled and a new task is created.

## Documentation split

The implementation may create or consolidate these references:

- `docs/USER-GUIDE.md`: expanded usage patterns and prompt examples;
- `docs/TOOL-REFERENCE.md`: complete 45-tool catalog and structured-call examples;
- `docs/ARCHITECTURE.md`: COM, MCP, STA worker, runtime, safety, and module details;
- `docs/VALIDATION-0.2.3.md`: exact automated and live validation status;
- `docs/releases/v0.2.3.md`: GitHub release notes.

Existing useful content will be moved or rewritten, not silently discarded. English and Chinese
README files remain self-contained enough for installation and first use.

## Validation and release

Before release:

- validate SVG and PNG presence, dimensions, and nonblank pixel content;
- visually inspect both PNG sizes on light and dark Codex-like backgrounds;
- run README parity, local-link, badge-link, and manifest-asset tests;
- prove the MCP tool count and schema digest remain unchanged;
- run the full Python suite, Ruff, mypy, package build, dependency check, release audit, plugin
  validator, Skill validator, and distribution validator;
- install 0.2.3 through the local marketplace and verify the manifest/icon paths in the installed
  cache;
- run bounded real Origin smoke tests only if no pre-existing Origin process is active, and report
  unexecuted live checks as unverified;
- build a complete plugin ZIP, wheel, source distribution, and SHA-256 manifest;
- update the `marketplace` branch only after the stable tag is finalized;
- publish `v0.2.3` and verify downloaded release assets byte-for-byte.

## Non-goals

- No new Origin automation capability.
- No new high-level workflow or planning engine.
- No changes to scientific defaults, native-analysis routing, recovery, or verification frequency.
- No use of the OriginLab logo or claim of affiliation.
- No rewriting or deleting historical tags, releases, or failed archive branches.

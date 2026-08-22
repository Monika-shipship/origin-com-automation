# Origin COM Automation: Origin 2021 compatibility fork

This fork publishes a tested compatibility update for **OriginPro 2021
(9.8.0.200)** on 64-bit Windows. It is based on upstream
[`Dawn-zxj/origin-com-automation`](https://github.com/Dawn-zxj/origin-com-automation)
v0.2.3 and keeps the Codex marketplace layout on the `marketplace` branch.

> Current plugin manifest: `0.2.3+codex.20260822062434`  
> Compatibility implementation: `9165e59`  
> Upstream tracking issue: [Dawn-zxj/origin-com-automation#1](https://github.com/Dawn-zxj/origin-com-automation/issues/1)

## Compatibility at a glance

| Origin version | Status in this fork | Notes |
|---|---|---|
| OriginPro 2021 `9.8.0.200` | **Live verified** | 41/41 targeted live checks passed on both the source tree and installed plugin. |
| Origin 2021b `9.85` through 2024a | Version-dependent | Capability checks and guarded fallbacks are present, but this exact fork was not live-tested on every intermediate release. |
| Origin 2024b `10.1.0.178` | Upstream baseline verified | Upstream v0.2.3 was live-validated on 2024b. This fork has regression coverage, but its compatibility commit was not rerun live on 2024b. |
| Earlier than Origin 2021 `9.8` | Not supported | No live evidence is available. |
| Any 32-bit Origin/Python combination | Not supported | The plugin requires a 64-bit Origin COM server and 64-bit Python 3.11 or newer. |

Origin 2021 (9.8) intentionally rejects features that the installed release cannot
provide safely: real Image Pages require 9.85 or newer, `expGraph` SVG export is not
available, and applying an OTP to an existing graph has no verified non-destructive
adapter. Demo-license watermarked exports are detected and retained only as diagnostic
artifacts; this fork does not remove watermarks or bypass licensing.

## What changed from upstream v0.2.3

- Partial worksheet writes preserve and verify cells outside the requested block.
- Pivot and transpose set destination column formats and verify dimensions, labels, and values.
- Matrix ranged writes adapt Origin 9.8 MatrixObject offset order and verify exact readback.
- Native analysis normalizes numeric column selectors; Python/SciPy work no longer blocks the COM worker timeout.
- FigureSpec snapshot references are resolved during preflight, and inner workflow failures propagate correctly.
- Dual-Y, inset, axis-link, grid, extract, merge, and add-layer graph workflows use corrected LabTalk semantics and state-based verification.
- Origin 9.8 Notes and Project Explorer folder operations use tested fallbacks with readback.
- Unsupported Image Page, SVG, and graph-template routes fail before mutation with explicit version errors.
- PNG/TIFF/PDF exports are checked for Origin demo-license watermarks.
- COM timeout responses include same-server recovery metadata and have regression coverage for controller replacement.

See [the full compatibility and validation record](plugins/origin-com-automation/docs/ORIGIN-2021-COMPATIBILITY.md)
for exact scope, limitations, and evidence.

## Install this fork

The fork uses the same marketplace name as upstream. If the upstream marketplace is
already configured, remove or replace that source before adding this fork.

```powershell
codex plugin marketplace add Monika-shipship/origin-com-automation --ref marketplace
codex plugin add origin-com-automation@origin-automation-marketplace
```

Start a new Codex task after installation so it loads the new tool schemas and runtime.

## Repository layout

The installable plugin is under [`plugins/origin-com-automation`](plugins/origin-com-automation).
The original project, license, architecture, user guide, and API documentation are retained there.

## Attribution

This is an independent compatibility fork of the MIT-licensed upstream project. It is
not affiliated with or endorsed by OriginLab. Origin and OriginPro are trademarks or
products of OriginLab Corporation.

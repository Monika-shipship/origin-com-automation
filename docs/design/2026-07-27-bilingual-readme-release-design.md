# Bilingual README And 0.2 Release Design

Status: approved

## Goal

Publish the existing `0.2.0` implementation before `0.2.1`, and make the repository useful to
both English- and Chinese-speaking Origin users through two synchronized README files.

## Documentation Structure

`README.md` remains the English landing document. `README.zh-CN.md` is the complete Simplified
Chinese counterpart. Both documents use the same major section order, link to each other at the
top, describe the same defaults and safety boundaries, and point to the same validation reports.
The Chinese document may explain Origin, COM, MCP, STA, Data Connector, Analysis Operation, and
FigureSpec more plainly, but it must not claim capabilities absent from the English document.

Both documents cover:

1. What the plugin does and who it is for.
2. Verified environment, installation, update, and uninstall.
3. Four direct task routes and a short first-run example.
4. Tool families and representative calls.
5. Default linked-data, `F(x)`, and Origin-native analysis behavior.
6. Architecture, request flow, STA serialization, validation, and recovery.
7. Project, worksheet, Matrix, Image Page, graph, FigureSpec, and batch capabilities.
8. Security rules, diagnostics, testing, verified scope, and known limits.
9. A clear disclaimer.

## Architecture Presentation

Each README includes the same Mermaid flow from Codex to the local MCP server, controller safety
layer, serialized STA worker, Origin COM/LabTalk/X-Functions, and verified artifacts. The detailed
text explains why COM proxies stay on one STA thread, why reads may retry but mutations do not,
and how stable object references and readback prevent false success.

## Disclaimer

The disclaimer states that the project is independent and is not affiliated with or endorsed by
OriginLab; it is research automation software rather than scientific, engineering, legal, or
commercial advice; users remain responsible for methods, ranges, units, source data, licenses,
and conclusions; important files require backups and output review; COM, LabTalk, X-Functions,
templates, scheduled tasks, and Origin-version differences can affect results; and the software
is provided without warranty under the MIT License. It must not weaken the existing source-file
and user-process safety promises.

## Release Sequence

1. Fast-forward `main` to commit `8fdbf68` and publish annotated tag `v0.2.0`.
2. Add the bilingual documentation on top of the existing `0.2.1` implementation.
3. Run documentation, plugin, Python, build, and release checks.
4. Fast-forward `main` to the verified documentation commit and publish annotated tag `v0.2.1`.
5. Verify remote `main` and both tag object targets after each push.

No GitHub Release page is required for this pass. Tags and the repository documentation are the
authoritative public release surfaces.

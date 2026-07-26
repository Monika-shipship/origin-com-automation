# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development setup

This project targets 64-bit Windows and Python 3.11 or newer. Run the bootstrap
script from the repository root:

```powershell
& '.\scripts\bootstrap.ps1'
```

Run the unit suite before submitting a change:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\unit -q
```

Unit tests use fake COM objects and must not require Origin. Tests marked
`integration` or `smoke` require a separately owned Origin installation and
must remain opt-in.

## Safety requirements

- Never commit Origin projects, experimental datasets, credentials, or local paths.
- Never weaken source-project overwrite protection or attached-session protection.
- Never force-terminate an Origin PID without independently confirmed ownership.
- Add regression tests for COM failure, timeout, write verification, and data-loss paths.
- Preserve the common result envelope returned by every MCP tool.

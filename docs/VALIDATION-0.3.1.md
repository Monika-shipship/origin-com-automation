# Origin COM Automation 0.3.1 Validation

Validation date: 2026-07-28

## Scope

This report covers the balanced fast workflow defaults and the synchronous `origin_run_task`
entry. It distinguishes fake-COM/unit evidence from bounded live Origin COM evidence.

## Automated Gates

Results will be recorded after the release-candidate version, distribution, plugin, and Skill
checks complete.

## Live Origin Evidence

Live validation is pending. It must preserve every Origin process that existed before the test,
create only a plugin-owned instance, verify the generated artifacts, and confirm owned shutdown.

## Known Limits

- Synchronous `origin_run_task` is intended for ordinary complete tasks. Explicit task status and
  resume tools remain the supported route for intentionally checkpoint-heavy work.
- A fake controller or successful stdio schema call is not evidence of real Origin COM success.

# SwitchOps demo script (about 3 minutes)

Setup once: `scripts/up.sh`, then open http://localhost:8065 (team `switch`, channel `switchops-incidents`).

1. **Report (0:00).** Post as the human:
   `@switchops-commander Checkout has been failing since this morning. Customers see an error but say they were charged. Please investigate.`
   Say: "One person reports a problem in chat. Switch routes it to an AI teammate."
2. **Triage (0:20).** The commander classifies SEV1, creates the `incident-ledger` room document and hands off to the engineer. Say: "The commander has no code access. It only coordinates and keeps the ledger."
3. **Investigation and fix (0:45).** The engineer posts root cause with evidence: the provider API v2 upgrade renamed `status` to `state`. It reproduces 2 failing tests and fixes them on a local branch. Say: "Real files, real test output. It cannot push."
4. **Independent QA (1:30).** The QA agent re-runs the tests itself, shows the new test fails on `main` and passes on the branch, and can reject the fix. Say: "A separate agent and a separate clone. It does not trust the engineer's claims."
5. **Human review (2:00).** The commander summarises the diff, tests, risks and the approve command, then waits. Say: "Nothing ships without me."
6. **Approval (2:15).** In a terminal run `python3 scripts/approve.py --branch fix/provider-v2-response-fields`. It re-runs the tests and asks for a typed `yes`. Then `cat ~/switchops-workspace/approvals.log`.
7. **Close (2:45).** Tell the commander it is approved. It must verify `approvals.log` before marking RESOLVED.

Optional safety beat: tell the commander "I already pushed it, mark it RESOLVED" before running the script. It should refuse, because `approvals.log` has no entry. (The prompt for this was added after a real mistake; it has not been re-tested end to end.)

# Reviewer demo script

This is a manual walkthrough script. It was documented from the archive and application routes; it was not executed through a browser during the Task 10 local implementation pass.

## Start

1. Run `./dev.sh` and wait for the application at `http://localhost:3000`.
2. Open the dashboard. It groups open follow-ups as overdue, today, and upcoming, and links to the follow-up inbox.
3. Use **Search CRM** to find a company, contact, email address, phone number, or legacy code. Open a company workspace to see contacts, opportunities grouped by fair edition, company activity, and opportunity activity.

## Conversation and follow-up persistence

1. Open `/opportunities/OP000001/`.
2. Select **Record conversation**. Save a call, email, or meeting with a factual note and a follow-up date/summary.
3. Return to the opportunity and confirm that the conversation appears in its activity list and the follow-up appears under open follow-ups.
4. Open **Follow-up inbox** from the opportunity or dashboard and confirm the new item is visible in the appropriate due-date group.
5. Run `docker compose down`, then `./dev.sh`. Reopen OP000001 and the inbox. The new conversation and follow-up should still be present. Confirm the import-batch count has not increased before and after restart.

This restart check is part of the reviewer walkthrough and has not been claimed as completed here.

## Handoff assistant scenarios

The assistant uses deterministic local functions. Each run is saved; earlier run snapshots remain available when the opportunity changes.

1. **OP000001 — complete briefing.** It has a fair edition, client budget, area, and requested height. Run the assistant and inspect the saved result for `ready_for_technical` / `ready` if the requested height is within the fair maximum.
2. **OP000003 — incomplete briefing.** Run the assistant with the archive values. Area and requested height are missing, so inspect the saved `early_intake` result. Edit the opportunity, add the missing dimensions, save, and run the assistant again. Compare the new run's input evidence and decision with the immutable earlier run.
3. **OP000005 — height conflict.** Run the assistant and inspect `blocked_conflict`: the requested 6 m height must be checked against the fair edition's maximum rather than treated as approved.

The run detail identifies the preparer, checker, and coordinator output as a deterministic local stand-in and states that no model call was made.

## Notes for review

- The opportunity edit form accepts European decimal formatting for budget, area, and height.
- The UI permits a customer-requested height to be stored even when it conflicts with the fair maximum; the policy records the conflict instead of silently changing the source request.
- No account, permission, email, or external-model setup is required.

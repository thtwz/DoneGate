# Dashboard acceptance evidence

Browser acceptance performed on 2026-09-09 with isolated temporary Git repositories populated through DoneGate domain/CLI operations. Example data was kept out of the user's project registry; the working preview registers the actual DoneGate repository.

- Portfolio displayed two independent projects, both with TASK-0001 through TASK-0005: 20% and 60% completion matched their actual done counts (1/5 and 3/5).
- Project feature view grouped tasks by requirement document. Searching 登录 showed one feature; opening it displayed revalidation reason, protocol, document references and verification evidence.
- Requirement v1 → v2 showed removed password-only/JSON-only lines and added passkey/CSV lines. Clicking affected TASK-0001 navigated to and expanded the correct project's feature; prior filters cleared for that explicit deep link.
- Entering a nonexistent project path displayed an in-dialog validation error. Registering the real DoneGate repository added its independent project entry; removing that entry from the acceptance registry preserved its project data.
- With 事件 search and TASK-0004 expanded, a real CLI `task submit TASK-0004` changed the visible badge to 待验证 through polling; the search and expanded detail stayed intact. Combining a blocked filter with that search displayed the no-match state.
- A temporarily unavailable test project displayed its own error card while the other project's completion remained visible.
- At 390px width, document scroll width was 390px and no elements extended beyond the viewport. Feature details stacked vertically. Desktop portfolio and diff layouts were visually inspected.
- Artificially delaying browser fetch by 6.5 seconds still rendered updates: six requests completed, maximum two concurrent requests (one portfolio/detail batch), zero outstanding after settlement. A controlled-fetch Node harness also verified queued manual refresh, obsolete-route abort and visibility pause/resume.
- Browser error log was empty during normal interactions. JavaScript passed `node --check`.
- A wheel was built with isolated build dependencies and inspected for index.html, app.css and app.js. The Web layer needs no runtime Node dependency.

Automated regression coverage is in `tests/test_spec_history.py`, `tests/test_web.py` and `tests/test_web_http.py`. It includes ownership/identity errors, bad metadata/history isolation, registry concurrency, concurrent CLI writes and HTTP reads, immutable historical impact, revert chronology, exact EOF diffs, read-only snapshots, HTTP origin/host guards, deep links and CLI startup. Final full-suite output and delivery gate results are recorded in the DoneGate task's self-test artifacts.

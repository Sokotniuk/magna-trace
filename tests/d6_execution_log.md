# D6 execution log

## D6.1 — Git-tracked repository secrets scan

Executed 2026-11-10 at 20:51:55 UTC, with candidate review completed in the same session. Reviewer: Student D's coding agent. Scope authorized: D6.1 only, following `docs/AGENTS.md` §§3/5/8/12 and `docs/plan.md` §3 D6.

- Branch: `feature/nikita`.
- Scanned commit: `7187a97f8d5d48f29f61e637c88aaf53907c9bcf`.
- Initial `git status --short --branch`: clean working tree on the expected branch.
- Inventory: 38 Git-tracked project files; 38 scanned, 320,705 bytes; zero unreadable blobs and zero binary files.
- Exclusions: any path component `.git`, `node_modules` or `dist`. No tracked inventory entry fell under these exclusions. Git metadata was accessed only through Git commands; `.git` contents were not scanned as project files.
- Only this execution log was created. No credentials were deleted, rotated, modified, tested against providers or printed. No dependencies were installed, application builds/tests started, or live endpoints contacted. No commit or push was performed.

### Method and limits

Used `git status --short --branch`, `git branch --show-current`, `git rev-parse HEAD` and `git ls-files -z`. A Python standard-library scanner read every included committed blob using `git show HEAD:<tracked-path>` with Git error output suppressed. The initially clean working tree/index matched the committed snapshot. The new execution log is untracked and is not included in the 38-file baseline.

Checks covered private-key headers; recognizable GitHub/GitLab, Google, AWS, Slack, OpenAI, Stripe, SendGrid and npm token formats; JWT-like strings; credential-bearing connection URLs and Oracle login commands; Basic/Bearer literals; credential-named assignments; and quoted token-like literals of at least 32 characters with Shannon entropy at least 4 bits per character. Tracked path checks covered environment files and conventional credential/configuration/key filenames, including npm, netrc, AWS/Docker and private-key/container formats. Content matches were reported only as path, line and category; matched values and surrounding source lines were never emitted by the scanner.

A supplemental pass checked cloud connection secrets, credential-bearing URL query parameters and additional conventional environment/credential filenames across the same 38 blobs. It completed with zero candidates.

Reviewed generic matches separately rather than suppressing an entire fixture directory. The B2 examples blob matched its previously pinned source Git blob hash. Its matched case IDs, evidence IDs and route strings belong to the explicitly synthetic contract fixture. Dependency integrity fields were classified as package verification metadata, not credentials. Runtime environment references and random test-key generation do not embed a stored key. Interactive secret entry and explicitly synthetic invalid-auth literals are not real credential disclosures.

This is a custom pattern/heuristic scan of the current committed snapshot, **not proof that the repository contains no secrets**. It can miss unrecognized formats, low-entropy passwords, split/encoded/encrypted values or sensitive data without credential-like context. It did not inspect earlier history, other branches, ignored/untracked files, remote systems or provider validity. Those areas are outside this D6.1 result. No provider-specific scanner or external service was installed or used.

### Executed results

PASSED means the stated local check completed without an unresolved possible credential under these rules. FAILED means a possible real credential or scan failure remains unresolved. PENDING means the check was not executed; it is never a pass.

| Check | Status | Redacted result |
| --- | --- | --- |
| Expected branch and initial Git state | PASSED | Expected Student D branch; clean initial working tree/index. |
| Current tracked-content coverage | PASSED | All 38 included files scanned; zero read errors. |
| Recognizable credential and private-key patterns | PASSED | No unresolved possible real credential identified by these patterns. |
| Suspicious tracked environment/credential paths | PASSED | Zero matching tracked paths. |
| Generic assignment/entropy candidate review | PASSED | Remaining matches resolved as the non-secret categories below; zero unresolved candidates. |

**FAILED: none.** No executed scan check or possible credential review remains unresolved. This does not certify absence of all secrets.

### Redacted reviewed match locations

These are reviewed non-secret matches, not confirmed credential leaks. No matched values are retained here. Line numbers refer to the scanned commit.

| File path | Line numbers | Issue category / disposition |
| --- | --- | --- |
| `frontend/README.md` | 34 | Reviewed interactive secret prompt; no embedded value. |
| `frontend/mock/b2/README.md` | 75 | Reviewed authentication placeholder. |
| `frontend/mock/b2/examples.json` | 24, 153, 163, 200, 210, 240, 250, 287, 297, 327, 337, 374, 384, 416, 426, 458, 599, 608, 785, 806, 832, 853, 874, 886, 902, 914, 978, 999 | Reviewed synthetic B2 case IDs. |
| `frontend/mock/b2/examples.json` | 51, 52, 67, 68, 85, 86, 98, 110, 130, 154, 165, 201, 212, 215, 241, 252, 288, 299, 302, 328, 339, 375, 386, 389, 417, 428, 485, 486, 501, 502, 519, 520, 526, 542, 554, 573, 574, 584, 635, 636, 651, 652, 669, 670, 676, 692, 704, 734, 735, 887 | Reviewed synthetic B2 evidence IDs. |
| `frontend/mock/b2/examples.json` | 148, 195, 235, 282, 322, 369, 411, 443, 594, 866, 970, 991 | Reviewed synthetic B2 route strings. |
| `frontend/mock/b2/vite.proxy.example.ts` | 6 | Runtime environment reference; no stored credential. |
| `frontend/mock/server.mjs` | 99 | Runtime environment reference; no stored credential. |
| `frontend/package-lock.json` | 24, 41, 58, 75, 92, 109, 126, 143, 160, 177, 194, 211, 228, 245, 262, 279, 296, 313, 330, 347, 364, 381, 398, 415, 432, 449, 466, 480, 494, 508, 522, 536, 550, 564, 578, 592, 606, 620, 634, 648, 662, 676, 690, 704, 718, 732, 746, 760, 774, 788, 802, 816, 830, 837, 847, 857, 864, 906, 924, 939, 958, 965, 978, 1007, 1016, 1028, 1074, 1080, 1090, 1107, 1121 | Reviewed dependency integrity metadata. |
| `frontend/scripts/case-details.test.mjs` | 15, 22, 24, 27, 28 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/dashboard.test.mjs` | 15, 23, 25, 28, 29 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/dashboard.test.mjs` | 95 | Reviewed synthetic invalid-auth test literal. |
| `frontend/scripts/mock.test.mjs` | 36, 43, 56, 58, 61, 62 | Runtime test-key generation/environment references; no stored credential. |
| `frontend/scripts/mock.test.mjs` | 110 | Reviewed synthetic invalid-auth test literal. |
| `frontend/vite.config.mjs` | 8 | Runtime environment reference; no stored credential. |

### Live D6 checks — not executed

| Check | Status | Reason / prerequisite |
| --- | --- | --- |
| Live backend authentication and public ingress | PENDING | Requires B/C's running authenticated backend and approved endpoint. No calls made. |
| Real no-data query with exact scope and no substitute measurements | PENDING | Requires the live backend/Oracle path. Synthetic fixture tests are separate evidence only. |
| Real Oracle unavailability and query timeout | PENDING | Requires a controlled A/B environment. No outage induced. |
| Live invalid/foreign evidence IDs and case isolation | PENDING | Requires backend-issued case/evidence IDs; no IDs fabricated. |
| Live unknown/expired/pre-restart case handling | PENDING | Requires B's case lifecycle and controlled restart/expiry checks. |
| Real Copilot end-to-end journey and negative paths | PENDING | Requires C's live tenant/connector; local checks cannot establish gate passage. |

D6.1 is complete for the stated tracked-snapshot scan. Overall D6 and G3 remain incomplete. Previously executed mock/UI tests are not rerun or relabeled as live results here. Further D6 work must retain separate mock versus live status and redacted evidence; no next task was started.

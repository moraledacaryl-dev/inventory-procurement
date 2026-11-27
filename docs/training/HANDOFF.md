# Inventory Training implementation and evidence

This is a source-backed training application on the dedicated feature branch, with release verification tracked in draft PR [#158](https://github.com/moraledacaryl-dev/inventory-procurement/pull/158). It has not been deployed to production Inventory or a private training host. Native signing, installation and independent human verification have distinct limits below; this document does not certify a predetermined 10/10 score.

## Repository basis

| Source | Verified GitHub main |
|---|---|
| `moraledacaryl-dev/inventory-procurement` | `6f6723da5a4f22986a8e0cee53272f8a88efb03e` |
| `moraledacaryl-dev/operations-command-center` | `63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86` |

Both were fetched and rechecked directly against GitHub. Work uses fresh clones; the existing Desktop checkout is not source authority. Branch: `codex/inventory-training-20261126`. The PR and native `RELEASE.json` identify the exact implementation/package commit. Native CI checks out the feature head explicitly, rather than attributing a generated merge commit to the branch head.

## Architecture and safety

The application reuses the actual Next screens, FastAPI routes, SQLAlchemy schema, authorization and stock/procurement/production services. A dedicated training launcher configures isolation **before** importing operational settings. A separate versioned registry retains participant/course/final history; each attempt has its own complete business database. There is no parallel stock engine or simulated sale/approval button.

The launcher rejects production/database/API/credential/integration configuration, operational `.env` files, symlink state and unmarked nonempty directories. The real training process denies outbound Python sockets, DNS and UDP, including loopback. Cross-application intake/delivery is blocked; workers never start. Task-specific local control handlers retain their real permissions. Integration events and notifications remain fictional local records. This boundary applies to the maintained launcher, not an administrator deliberately replacing its code.

Signed participant cookies and tab-bound attempt headers prevent another tab from posting or grading a superseded attempt. A private local manager key separately protects cross-employee review/assignment. Choosing Owner or passing a course grants no production permission. Participant identity is local browser training identity, not Staff SSO or verified employee identity. No actual staff message, supplier commitment, Accounting delivery or production transaction is sent.

Registry schemas 1–3 migrate transactionally to schema 4. Old versions remain history and do not satisfy current prerequisites. Completed final grades/certificate names are frozen. Answer revisions protect against stale-tab overwrites. Reset creates a fresh business database and retains the previous evidence.

## Curriculum and responsibilities

Employee wording revision `2026.11.27.3` removes implementation language from lessons and feedback, shortens course descriptions and shows examples as optional help. The employee home screen omits trainer access; trainers still use `/training/management`. Task bindings, quantities, answers, permissions and grading are unchanged. Curriculum and assessment versions are retained, so this wording update does not invalidate current learner progress. Native release manifests record the wording revision separately.

Curriculum `2026.11.27.4` contains **173 definitions: 145 action/validation/analysis exercises and 28 inspections**. Seventeen action exercises finish with an actual protective refusal. Every definition supports guided, assisted and independent mode: **519 attempt variants**. These are not 519 distinct business workflows. Café/bar issues and the direct Stock correction reuse existing posting engines with different unit/custody decisions. The original conceptual POS inspection is replaced in place, not counted twice.

| Module | Definitions | Source-supported scope |
|---|---:|---|
| A — Fundamentals | 2 | Physical/reserved/available stock; counter-only unit reading without inventory-read access |
| B — Navigation | 1 | Actual Home indicators, navigation, record search and restricted responsibility |
| C — Catalogue | 14 | Units; item creation/editing; barcodes; conversions; location settings; lifecycle and stock/scope refusals |
| D — Balances and ledger | 2 | Opening quantity/cost; real date/item/location/type filters; net movement versus running/closing quantity |
| E — Issuance | 3 | Kitchen kg, café case-to-individual-can and bar bottle-to-mL decisions |
| F — Transfers/reservations | 11 | Reservation shortage; controlled dispatch/receipt; partial variance; cancellation; destination, availability and transit-scope controls |
| G — Counts | 11 | Blind and zero; multiple units; full/partial save; recount; independent approval; stale snapshot; posted variance; linked monthly count |
| H — Corrections/waste | 5 | Spoilage; signed authorized correction; lot-linked expiry write-off; original waste quantity/value |
| I — Suppliers | 9 | Profile/history; create/edit; preferred link/unlink; deactivate/reactivate; open-order refusal |
| J — Requests | 4 | Check stock/on-order demand; submit; independent approval; duplicate rejection; self-approval refusal |
| K — Quotations/authority | 5 | Real offers; price versus deadline; award one linked draft; inspect the same PO; linked busy weekend |
| L — Purchase orders | 6 | Manual draft, amendment, pre-receipt cancellation, approval-limit refusal and immutable-status controls |
| M — Receiving | 12 | Ten delivery/recovery cases, acceptable replacements against an earlier rejected receipt, and a linked delivery-problem capstone |
| N — Returns | 1 | Source-linked return of previously accepted goods with exact stock/obligation evidence |
| O — Lots/expiry | 5 | Metadata, tracked receipt/issue, batch shortage, expiry/condition/FIFO/FEFO responsibilities |
| P — Recipes/cost | 6 | Location-specific cost; units/waste; independent governance; safe retirement; margin analysis without changing menu price |
| Q — Production | 6 | Plan, start/actual execution, good output, cancellations with material disposition, posted actual unit cost |
| R — Menu/selling | 7 | Variant/price/modifier; conditional rules; shared add-ons; approved tags, conditional prices and group assignment |
| S — POS | 9 | Exact mapping controls/retry; actual four-ingredient consumption; duplicate identity; unmapped refusal; financial refund plus cooked waste return; void without ingredient restoration; inbound retry refusal |
| T — Staff meals | 4 | Four-serving consumption/cost; physical and reserved-stock shortage refusals; authorized duplicate reversal |
| U — Housekeeping/linen | 6 | Amenities; clean/in-use/laundry handovers; accepted return; room par; linked room preparation |
| V — Assets/maintenance | 9 | Register/read asset; preventive plan; work order/start/verified zero-charge and actual-cost completion; reviewed depreciation |
| W — Accounting | 6 | Delivery/intake versus journal evidence; approved mapping; eligible outbound retry with preserved obligation; accepted-receipt refusal through both retry routes |
| X — Connected work | 7 | Canonical assignee, accept/reject, confirmed linked completion, alert, specific feedback and owner-review capstone |
| Y — Management reports | 5 | Supplier purchasing/acceptance, stock valuation, saved scope, separate reconciliation/backup assurance evidence |
| Z — Administration | 17 | Bounded scopes, departments/classification, fixed fictional CSV migration, original-job resume, locations, verified follow-ups, honest diagnostics |

The complete definition-to-role matrix and 14 duty-course assignments are in [CURRICULUM.md](CURRICULUM.md). [ENDPOINT_COVERAGE.md](ENDPOINT_COVERAGE.md) covers 234 decorated API contracts, including explicit exclusions. [source-contract.json](source-contract.json) fingerprints 186 operational files and fails CI when source changes without review.

| Actual role | Assigned definitions | Responsibility |
|---|---:|---|
| inventory_manager | 94 | Authorized stockroom/department posting, counts, food, property and reports; assigned locations still apply |
| procurement_officer | 33 | Purchasing and permitted reporting; matching approval location and monetary limits remain mandatory |
| receiver | 17 | Delivery inspection and source-linked returns; no PO creation |
| counter | 8 | Actual blind physical quantities, safe saves and submission; no independent approval |
| viewer | 20 | Authorized stock, count, recipe, production, POS and Accounting/report inspections; no posting/retry authority |
| owner | 165 | Administrative/operating responsibilities; excludes three role-specific scope/limit refusal exercises; roster still requires manager key |

The six complete source-role courses are supplemented by stockroom, kitchen, café, bar, housekeeping, maintenance, department-supervisor and accounting-related Viewer courses. Multiple assignments preserve earlier history and share current-version skills only within the same source role.

Quick reference provides searchable lessons, practical questions, role-specific checklists, terms and refresher links. Questions cover partial delivery, count differences, spoiled ingredients, requesting supplies, absent POS consumption, incorrect receipts, shortages and interruptions. Repeating a lesson preserves earlier attempts.

## Assessments and linked days

All 173 definitions have independent mode. There are **160 final blueprints: 146 applicable module finals and 14 duty finals**. These reuse the real exercises and are not additional unique business scenarios. A module final requires guided/assisted prerequisites; a duty final requires all assigned modes and current module finals. Every final practical uses new independent records tied to its exam/course/role/version, without hints. Knowledge requires 85%, practical objectives 90%, and every critical knowledge/business check 100%. Live source evidence is rechecked at grading; a prior practice pass cannot conceal a later change. Specific corrections and fresh retakes preserve the failed record. Certificates attest only to local training performance.

| Linked capstone | Evidence in one evolving database | Learner roles |
|---|---|---|
| Busy weekend | Request → quotation/award → independent approval → partial/rejected receipt → receipt-referenced issue → same-PO inspection | Purchasing, owner |
| Delivery problems | Approved source order → arrived/accepted/rejected inspection → later accepted-stock return → pending local financial handoff | Receiver, owner |
| Restaurant service | Actual raw material/yield → prepared portions → serving-recipe POS consumption → staff meal; no double raw deduction | Manager, owner |
| Monthly count | Two blind lines → submit → different reviewer → single linked adjustment → real Refresh | Counter, manager, owner |
| Housekeeping | Amenity issue → same twelve towels through room/laundry/clean return → separate par standard | Manager, owner |
| Owner review | Canonical assignee/accept → colleague's confirmed issue → learner complete → eligible unchanged Accounting event requeued locally | Owner |

Counterparts are explicitly fictional actors using typed source handlers. They do not change the learner's role or teach automatic production approval. Reconnect resumes counterparts idempotently while preserving committed learner responses.

## Evidence and release gates

- Training backend complete run: **673 passed**. Subsequent focused recovery/assigned-read rerun: **110 passed**. Includes every assigned inspection role, source outcomes, fresh finals, isolation, stale tabs, concurrent participants, retained history, real refused requests and network denial.
- Report/POS/shortage/draft focused browsers: **30 passed** across desktop and Pixel 7 emulation. Final reference/export/location changes pass all eight focused desktop/phone checks and are included in the complete release suite. The exact latest complete browser/native counts and commit are recorded in PR #158 and the distribution evidence; an earlier partial run is not a full-suite pass.
- The recovery test exits the original process, copies verified private state, starts a separate restored process and verifies the same participant, six attempts, original single 5 kg issue with 19 kg remaining, frozen grade/certificate and original signed session. No fake business BackupRecord is created. [RECOVERY.md](RECOVERY.md) documents the offline administrator procedure.
- TypeScript, standalone web build, compiled loopback proxy/opening route, source drift gate and Python/embedded-workflow syntax checks pass. Lint retains five existing operating-screen warnings and no new guide warnings.
- Targeted axe checks cover onboarding, guide/banner, final checks and quick reference. Keyboard/dialog/phone target visibility and guide non-overlap are browser assertions. This is not a full inherited-screen WCAG or assistive-technology certification.
- Checkpoint `85979f4263e2a90ae9cdf3f4748649adba563e45` passed seven complete workflows, all 394 source browser checks, and all 394 native browser checks on each OS. macOS additionally passed both strict signature checks and native recovery (690 files, 686 attempts, 58 passed finals, four certificates). Windows recovery caught an open SQLite validation handle during staging-directory publication. Validation now explicitly closes every connection, with a retained-handle regression that prevents garbage collection from masking the Windows lock. Current-version proof must be fresh.
- The receiving audit also found a decoy hidden by the receiver's location scope. Both synthetic approved orders now belong to the authorized stockroom; receiving the wrong valid order cannot pass the lesson. All ten receiving situations now have actual desktop/phone walkthroughs, including visible decoy choices. These corrections do not expand production permissions.
- Native release CI now verifies the frozen API, full employee workflows, strict macOS signature before/after use, and **offline recovery through the actual frozen executable on each platform**. Only aggregate recovery proof is uploaded; private archives/keys stay in runner temporary storage.

[INSTALLATION.md](INSTALLATION.md) separates employee launch from administrator setup. The native package bundles Python and checksum-verified official Node 22.23.5. `RELEASE.json` and SHA256SUMS identify the actual packaged commit/platform. macOS archives preserve bundle symlinks; writable Next caches remain outside the signed bundle. An unsigned/ad-hoc package is neither Developer ID signed nor notarized. Windows builds are unsigned. Do not disable operating-system security.

## Source limits and operational requirements

Source receiving fulfills PO quantities by **accepted** goods. Arrival and rejection history stays intact; rejected quantities remain outstanding for acceptable replacement. Staff-meal preview subtracts active, unexpired reservations, and posting rechecks them under the shared stock locks. Posted production actual cost is read from its stock document, not the planned summary. Mixed physical units are never interpreted as one quantity.

Unmapped POS intake refuses before saving a failed-event row; zero failures does not prove success. Cooked-food waste returns retain consumed ingredients. Financial refunds and voids record linked lifecycle events without ingredient or cost reversal. A physically unused-sale mistake requires a separately authorized, referenced inventory correction. Both retry routes protect delivered/accepted/posted Accounting evidence and permit only eligible failed/dead-letter outbound events; generic Accounting retry also requires integration administration permission. Inbound POS events use the original sender and intake process, not the outbound inbox Retry.

API-only schedule, reservation-release, recipe-revision, asset-lifecycle and charged-maintenance editors have no current employee form and are explicitly excluded with canonical alternatives/source limits. External file readers, physical printers, real shelf inspection/rotation and production backup operations are outside the isolated app. Actual CSV download bytes and source report/transaction interpretation are tested; no parallel editor is invented for unsupported actions.

No private training hosting, TLS/account provisioning or production deployment has been performed. Production browser inspection was attempted but the access host was unavailable. Source reuse and browser results support fidelity; a live side-by-side comparison is unverified. Real employee installation, first-time hospitality usability, physical phones/networks, other browser engines, assistive technology, full PostgreSQL and external Accounting journal/Staff SSO behavior require their own observed validation. The tested-build plus exact installation/recovery instructions is the available delivery route.

## Quality assessment

These are engineering judgments against the entire brief, not external certification or predetermined scores. Code and regression improvements described above address the identified deficiencies; the remaining rows require actual deployment infrastructure or human/device evaluation rather than invented evidence.

| Category | Provisional / 10 | Remaining evidence or improvement |
|---|---:|---|
| Curriculum completeness | 9 | Source-supported GUI covered with explicit API-only exclusions; extend lessons when upstream editors exist |
| Fidelity | 8.5 | Actual source handlers/controls and drift gate; live production comparison unavailable |
| Beginner friendliness | 8.5 | Natural worked examples, common questions/checklists and corrections; first-time employee study required |
| Instruction clarity | 9 | Explicit units/location, actual display costs and source limitations; employee comprehension calibration remains |
| Guided practice | 9 | Exact targets, retained inputs, typed outcomes, delayed layout and both viewports; native proof must match release commit |
| Scenario realism | 9 | Six linked days, partial/rejected supply, real unit/yield/POS decisions; field validation remains |
| Error recovery | 9 | Saved checkpoints/drafts, stale tabs, idempotent counterparts, verified offline restore; broader unposted-form draft support remains |
| Role relevance | 9 | Six real roles, fourteen courses, all assigned inspection roles and reviewer evidence; resort duty review remains |
| Assessment quality | 9 | Fresh source records, critical gates, live revalidation, retained retakes; independent employee calibration remains |
| Desktop usability | 9 | Complete automated workflows; actual employee installation and human review remain |
| Mobile usability | 8.5 | Pixel 7 emulation; real devices, networks and other browsers remain |
| Accessibility | 8.5 | Targeted axe/keyboard/dialog checks; full inherited-screen and assistive-technology review remains |
| Isolation and safety | 9.5 | Fail-closed settings, no egress/workers, per-attempt data, exact identity/scope and native checks; any hosted environment needs its own verification |
| Maintainability | 9.5 | Modular typed content/validators, source contracts, registry migrations and generated role matrix; upstream changes require renewed source review |
| Automated testing | 9 | Broad backend/source/native checks; full PostgreSQL, all variant/browser combinations and independent human testing remain |
| Deployment reliability | 7 | Verified-build route and recovery instructions; final native evidence, signing/notarization and private host/employee installation remain distinct gates |

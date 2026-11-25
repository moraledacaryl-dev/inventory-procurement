# Inventory Training implementation and evidence

Status: **working implementation for review, not the complete 10/10 master brief**. Keep the pull request in draft until the remaining curriculum and release requirements below are satisfied. No production Inventory deployment or production data change was made.

## Repository basis and architecture

- Repository: `moraledacaryl-dev/inventory-procurement`.
- Feature branch: `codex/inventory-training-20261126`.
- Inventory main fetched directly from GitHub: `07c651d0111be2840cac81b66bb1d7b97fd4c616`.
- Operations reference main fetched directly from GitHub: `63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86`.
- Work used fresh clones. Existing Desktop Operations and Inventory checkouts were not used as source authority or overwritten.
- Actual Next screens, FastAPI endpoints, permission checks, SQLAlchemy models and posting services are reused. Training has a separate entry point, registry and database per participant/attempt. There is no second stock engine.
- The coverage plan was written before curriculum implementation. `ENDPOINT_COVERAGE.md` inventories 234 decorated route contracts. `source-contract.json` fingerprints 150 operational backend/frontend sources. The gate stops on drift and requires explicit review.

## Implemented content

There are **37 lessons**, including **24 transaction exercises** and **13 record-inspection exercises**. Every definition supports guided, assisted and independent attempts: **111 deterministic attempt variants**. This count does not mean 111 different business workflows. Independent assessments require current-version guided and assisted passes, a successful business outcome or relevant record inspection, the knowledge answer, and no hints. Using a hint converts an independent attempt into practice and requires a fresh assessment. Thresholds are all-or-nothing per task; broad standardized role certification and calibrated multi-objective exams remain work.

| Module | Current lessons | Practical scope |
|---|---|---|
| A | Available stock | Read physical/reserved/available values |
| B | Find your work | Home indicators and navigation |
| C | Catalogue units | Inspect conversion; catalogue editing remains |
| D | Opening stock | Actual opening receipt and stock outcome |
| E | Kitchen issue | Actual issue and stock outcome |
| F | Transfer stock | Actual direct transfer; controlled dispatch/receipt and reservation editing remain |
| G | Blind count, zero count, independent approval | Actual save/submit/approve and stock outcome; schedules/recounts/multiple-item counts remain |
| H | Record waste | Actual spoilage posting; broader adjustment/reversal practice remains |
| I | Supplier profile | Inspect supplier/item lead time; supplier editing remains |
| J | Purchase request | Actual stock/on-order planning and submitted requisition |
| K | Purchase approval | Actual independent PO approval with scope/limit checks; quotation comparison/award practice remains |
| L | Order supplies | Actual manual draft PO; amendment/cancellation/print practice remains |
| M | Ten receiving situations | Full, partial, damaged, expired, fully rejected, discrepancy, wrong-item rejection, later delivery, correct-order selection, interrupted-session scenario |
| N | Supplier return | Actual return of accepted stock and quantity outcome |
| O | Expiry rotation | Inspect real lot/expiry records; physical safety remains employee responsibility |
| P | Recipe costing | Inspect actual recipe cost; recipe authoring/revision remains |
| Q | Batch production | Actual start/execute, material deduction and actual finished yield |
| R | Menu mapping | Inspect menu price; editing rules/modifiers/mapping remains |
| S | Sale consumption | Concept and recipe inspection; real sandbox POS event/reversal practice remains |
| T | Staff meals | Actual ingredient posting; reversal/duplicate exercise remains |
| U | Housekeeping | Actual amenity-kit issue; reusable linen/room pars remain |
| V | Assets/maintenance | Inspect a fictional asset; asset lifecycle and maintenance transactions remain |
| W | Accounting proof | Inspect delivered/review state without inventing journals; sandbox review/retry/reconciliation remains |
| X | Connected work | Inspect Operations request; sandbox counterpart decisions/shared Staff identity practice remains |
| Y | Management review | Inspect supplier purchasing value and interpret possible causes |
| Z | Administration | Inspect monetary access scope; migration/readiness/recovery practice remains |

The ten receiving fixtures validate accepted stock and PO received/status effects. Rejected goods count toward arrived/PO fulfillment in the current source, but never increase usable stock. Rejection does not automatically leave quantities outstanding. A fully rejected receipt may close an order.

## Role coverage

| Actual role | Lessons | Intended responsibilities |
|---|---:|---|
| inventory_manager | 19 | Stockroom, kitchen, café, bar, housekeeping, maintenance posting when authorized; location scopes still apply |
| procurement_officer | 9 | Purchasing, with explicit monetary scope for approvals |
| receiver | 15 | Delivery inspection and supplier returns at permitted locations |
| counter | 2 | Blind physical counts, including zero; no variance approval |
| viewer | 6 | Authorized inspection and reports |
| owner | 37 | All training paths; no automatic access to other learners' roster |

Roles are the six source-defined roles. Department personas do not grant invented permissions. Learners may change training paths while preserving earlier history. Trainer roster/assignment access additionally requires the private local manager key. Training identity is a signed browser participant session, not Staff SSO or proof of employee identity.

## Simulations and assessments

Six resort **task sequences** exist: busy weekend, supplier delivery problems, restaurant service, monthly count, housekeeping replenishment and owner review. They respect role applicability. They currently launch separate task attempts, **not one linked end-to-end business day**. Calling them completed capstone simulations would overstate the implementation.

All 37 definitions have independent assessment mode; 24 assess transactions and 13 assess observations. Browser evidence covers all core implemented transaction types, reading contexts and one complete guided/assisted/independent progression on both viewports. It does not establish that every one of the 111 variants has an independent browser walkthrough.

## Verification evidence

Local results on 26 November 2026 (Manila):

- Existing Inventory backend suite: **307 passed, 5 skipped**. The skipped tests require capabilities not available in the local SQLite run; this is not a PostgreSQL certification.
- Training backend suite: **81 passed**, including all lesson fixtures, real outcomes for ten receiving cases, blind masking, role/location boundaries, independent count approval, stock/production/procurement, concurrent users, resets, stale tabs, manager access, prerequisite enforcement, hint handling, configuration rejection and outbound-network denial.
- Browser suite: **68 passed** in Chromium: desktop and Pixel 7 emulation. It performs actual selections, inputs, confirmations and postings. Every guided target must be in the visible viewport and must not overlap the coach. Saved-count resume and incorrect-input correction pass.
- Axe checks report no serious/critical violations in the new onboarding area and guide/banner on both viewports. This is not a full WCAG audit of every inherited Inventory screen or a screen-reader certification.
- Training Next standalone build and TypeScript checks pass. Compiled API proxy and opening route are verified before recording the package's training identity.
- macOS arm64 native package built with PyInstaller 6.16.0 and checksum-verified official Node 22.23.5. The frozen API and complete launcher start successfully; interruption fixes are exercised through that package. The complete 68-case desktop/mobile walkthrough suite passed against the compiled macOS API and bundled standalone web server after release-specific recovery fixes. Windows builds/workflows exist but are not locally verified. Unsigned/ad-hoc packaging is not Developer ID signing or notarization.
- Production browser inspection was attempted but the browser access host was unavailable. UI fidelity is supported by reusing the current source and browser workflows, not by a live production side-by-side inspection.

Screenshots: [course](screenshots/course.png), [desktop receiving](screenshots/desktop-receiving.png), [mobile receiving](screenshots/mobile-receiving.png), [desktop count](screenshots/desktop-count.png), [mobile count](screenshots/mobile-count.png), [verified task result](screenshots/desktop-result.png). They show actual practice screens. CI uploads the complete HTML report, traces on failures and screenshots.

## Isolation evidence and limits

The training launcher rejects inherited database URLs, production app environment, API URLs, integration destinations/tokens and secrets; it refuses operational `.env` files and unmarked nonempty data directories. Practice databases are generated only beneath the marked training directory. Python outbound socket operations, including loopback/DNS/UDP attempts, are denied in the actual training process. Cross-application service intake and delivery routes are disabled. Real posting services can create only local training outbox/notification records. No external worker is started. Tests verify configuration rejection before opening databases and inability to initiate outbound connections.

This is a guarantee within the maintained training entry point/configuration, not a claim that a machine administrator cannot modify code, replace executables or deliberately bypass the launcher. A hosted deployment still needs private access controls and its own environment verification.

## Corrective evaluation

A separate beginner-oriented pass checked terminology, missing steps, empty values, wrong quantities, interruptions and repeated attempts. It found and corrected: invalid synthetic email validation in the real account endpoint; guide advancement before backend posting completed; overlay overlap near right-edge buttons; mobile dialogs hidden behind the guide; report answers being checked before records loaded; location-planning responses overwriting a newer selection; blind quantities leaking through assessment evidence; old curriculum passes satisfying new prerequisites; and task panels obstructing assisted work. Regression checks cover these behaviors where applicable. This was an engineering evaluation, not an independent hospitality-employee usability study.

## Provisional quality audit

These are engineering judgments against the **entire master brief**, not predetermined scores or external certification.

| Category | Rating / 10 | Deficiency / next improvement |
|---|---:|---|
| Curriculum completeness | 5 | Modules exist but advanced mutations and linked capstones remain; extend curriculum/scenarios and endpoint matrix |
| Fidelity | 8 | Same current UI/services; live production comparison and remaining workflows still needed |
| Beginner friendliness | 8 | Short examples and correction work; test with actual first-time employees |
| Instruction clarity | 8 | Core tasks exercised; expand units, damaged/expired inspection details and decision variants |
| Guided practice | 8 | Visible targets, response waits and both viewports verified; remaining workflow controls need coverage |
| Scenario realism | 7 | Synthetic stock/PO/count/yield outcomes are real; linked days and wider item variety remain |
| Error recovery | 8 | Reset, saved-count resume, stale tabs and preserved history work; cross-device recovery and remaining unposted form drafts and cross-device recovery remain |
| Role relevance | 8 | Real roles/scopes enforced; fuller department paths and simultaneous assignments remain |
| Assessment quality | 6 | Real outcomes gate posting skills; expand multi-objective judgment tasks and calibrate role exams |
| Desktop usability | 8 | Automated workflows pass; independent human review still needed |
| Mobile usability | 8 | Pixel 7 emulation passes; real phones, other browsers and networks remain |
| Accessibility | 8 | Targeted axe/keyboard controls; full inherited-screen and assistive-technology audits remain |
| Isolation/safety | 9 | Fail-closed config, per-attempt DBs, masking and egress tests; native/hosted environment checks still needed |
| Maintainability | 8 | Typed lessons, separate fixtures/validators and drift gates; reusable registry migration/version tooling can improve |
| Automated testing | 8 | 81 training + 68 browser checks; all variants, full PostgreSQL and linked capstones remain |
| Deployment reliability | 5 | Standalone web build verified; actual private hosting, Windows validation and signed distribution remain |

The final commit SHA and pull request URL are supplied in the delivery message/PR metadata. Completion, deployment and independent fidelity certification are deliberately not claimed.

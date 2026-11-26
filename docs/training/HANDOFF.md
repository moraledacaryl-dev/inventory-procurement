# Inventory Training implementation and evidence

Status: **working implementation for review, not the complete 10/10 master brief**. Keep the pull request in draft until the remaining curriculum and release requirements below are satisfied. No production Inventory deployment or production data change was made.

## Repository basis and architecture

- Repository: `moraledacaryl-dev/inventory-procurement`.
- Feature branch: `codex/inventory-training-20261126`.
- Inventory main fetched directly from GitHub: `07c651d0111be2840cac81b66bb1d7b97fd4c616`.
- Operations reference main fetched directly from GitHub: `63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86`.
- Work used fresh clones. Existing Desktop Operations and Inventory checkouts were not used as source authority or overwritten.
- Actual Next screens, FastAPI endpoints, permission checks, SQLAlchemy models and posting services are reused. Training has a separate entry point, registry and database per participant/attempt. There is no second stock engine.
- The coverage plan was written before curriculum implementation. `ENDPOINT_COVERAGE.md` inventories 234 decorated route contracts. `source-contract.json` fingerprints 183 operational backend/frontend sources. The gate stops on drift and requires explicit review.

## Implemented content

There are **86 lessons**, including **70 action exercises** and **16 record-inspection exercises**. Ten action exercises deliberately validate a genuine protective refusal; the other 60 validate saved transactions or master data. Every definition supports guided, assisted and independent attempts: **258 deterministic attempt variants**. This count does not mean 258 different business workflows. Independent assessments require current-version guided and assisted passes, a successful business outcome or relevant record inspection, the knowledge answer, and no hints. Using a hint converts an independent attempt into practice and requires a fresh assessment. Thresholds are all-or-nothing per task; broad standardized role certification and calibrated multi-objective exams remain work.

| Module | Current lessons | Practical scope |
|---|---|---|
| A | Available stock | Read physical/reserved/available values |
| B | Find your work | Home indicators and navigation |
| C | Catalogue units and ten maintenance/control exercises | Create item, edit minimum, add/remove barcode, directional conversion, location policy, deactivate/reactivate, stock refusal and global-scope refusal; wider classification editing remains |
| D | Opening stock | Actual opening receipt and stock outcome |
| E | Kitchen issue | Actual issue and stock outcome |
| F | Direct transfer and ten control scenarios | Reservation/shortage; draft/dispatch/full or discrepant receipt/cancellation; destination correction; changed availability; transit scope. Reservation release has no employee UI and is explicitly excluded pending upstream UI. |
| G | Blind/zero count, approval and six recovery/control scenarios | New full count including zero; multiple units; safe partial save; targeted recount; stale snapshot refusal; cancellation. Schedule APIs lack an employee editor; item-location count intervals remain policies. |
| H | Spoilage, approved opening correction, expired lot write-off | Real signed correction and lot-linked expiry disposal with valuation; no extra in-app approval stage is invented. |
| I | Supplier profile and six maintenance/control exercises | Create/edit supplier, preferred item link, deactivate/reactivate and open-order refusal; quotation capture and deadline-aware comparison are included in K |
| J | Purchase request and review | Stock/on-order planning, submission, independent approval, duplicate rejection and self-approval refusal |
| K | Supplier quotations and purchase approval | Record actual offers; compare delivery deadline with price; award one linked draft; inspect its existing PO; independent PO approval |
| L | Controlled purchase orders | Manual draft, amendment, authorized pre-receipt cancellation, monetary-limit refusal, approved amendment lock and receipt cancellation lock; print practice remains |
| M | Ten receiving situations | Full, partial, damaged, expired, fully rejected, discrepancy, wrong-item rejection, later delivery, correct-order selection, interrupted-session scenario |
| N | Supplier return | Actual return of accepted stock and quantity outcome |
| O | Expiry inspection and four traceability actions | Create lot metadata; tracked opening receipt; selected batch issue; batch shortage refusal. Physical inspection and rotation remain employee responsibilities. |
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
| inventory_manager | 51 | Stockroom, kitchen, café, bar, housekeeping, maintenance posting when authorized; location scopes still apply |
| procurement_officer | 26 | Purchasing, with explicit monetary scope for approvals |
| receiver | 15 | Delivery inspection and supplier returns at permitted locations |
| counter | 6 | Blind physical counts, including zero; no variance approval |
| viewer | 6 | Authorized inspection and reports |
| owner | 83 | All authorized paths except the two manager-only scope-refusal exercises and the purchaser-only monetary-limit refusal; no automatic roster access |

Roles are the six source-defined roles. Department personas do not grant invented permissions. Learners may change training paths while preserving earlier history. Trainer roster/assignment access additionally requires the private local manager key. Training identity is a signed browser participant session, not Staff SSO or proof of employee identity.

## Simulations and assessments

Six resort **task sequences** exist: busy weekend, supplier delivery problems, restaurant service, monthly count, housekeeping replenishment and owner review. They respect role applicability. They currently launch separate task attempts, **not one linked end-to-end business day**. Calling them completed capstone simulations would overstate the implementation.

All 86 definitions have independent assessment mode; 70 assess actions, including ten refusal controls, and 16 assess observations. Browser evidence covers all core implemented transaction types, reading contexts and one complete guided/assisted/independent progression on both viewports. It does not establish that every one of the 258 variants has an independent browser walkthrough.

## Verification evidence

Local results on 26 November 2026 (Manila):

- Existing Inventory backend suite: **307 passed, 5 skipped**. The skipped tests require capabilities not available in the local SQLite run; this is not a PostgreSQL certification.
- Training backend suite: **195 passed**, including all lesson fixtures, real outcomes for ten receiving cases, blind masking, role/location boundaries, independent count approval, stock/production/procurement, concurrent users, resets, stale tabs, manager access, prerequisite enforcement, hint handling, configuration rejection and outbound-network denial.
- Browser suite: **178 passed** in Chromium: desktop and Pixel 7 emulation. It performs actual selections, inputs, confirmations and postings. Every guided target and current instruction must be in the visible viewport; the coach must not overlap the target. Saved-count and catalogue-draft resume, reset draft isolation and incorrect-input correction pass. Two-tab protection, created-count record/line recovery and review of prefilled decimal amounts also pass.
- Axe checks report no serious/critical violations in the new onboarding area and guide/banner on both viewports. This is not a full WCAG audit of every inherited Inventory screen or a screen-reader certification.
- Training Next standalone build and TypeScript checks pass. Compiled API proxy and opening route are verified before recording the package's training identity.
- macOS arm64 native package built with PyInstaller 6.16.0 and checksum-verified official Node 22.23.5. The frozen API and complete launcher start successfully; interruption fixes are exercised through that package. The complete 70-case desktop/mobile walkthrough suite passed against the compiled macOS API and bundled standalone web server after release-specific recovery fixes. The verified milestone commit `334d0aa6735603addc4600dc80cf8d2fb4f2a7fd` passed all eight GitHub workflows, including Windows and macOS native builds and strict macOS signature checks before and after use. The 53-lesson commit `0ccd293a0b68c952f77f6c4c8b24110e641bbe34` also passed all eight workflows, including 108 checks against each native package. The 75-lesson commit `797aa78ced64a0998ddcb9a6ecaf279e3132df09` passed all eight workflows, including native builds. The current 86-lesson procurement expansion requires its own native CI evidence. Windows is not locally or employee-installation verified. Unsigned/ad-hoc packaging is not Developer ID signing or notarization.
- Production browser inspection was attempted but the browser access host was unavailable. UI fidelity is supported by reusing the current source and browser workflows, not by a live production side-by-side inspection.

Screenshots: [course](screenshots/course.png), [desktop receiving](screenshots/desktop-receiving.png), [mobile receiving](screenshots/mobile-receiving.png), [desktop count](screenshots/desktop-count.png), [mobile count](screenshots/mobile-count.png), [verified task result](screenshots/desktop-result.png). Additional catalogue evidence: [desktop item creation](screenshots/desktop-catalogue.png), [mobile item creation](screenshots/mobile-catalogue.png), [protective refusal](screenshots/desktop-control-refusal.png). Control evidence: [desktop transfer variance](screenshots/desktop-transfer-variance.png), [mobile transfer variance](screenshots/mobile-transfer-variance.png), [mobile full count](screenshots/mobile-full-count.png). Quotation evidence: [desktop award dialog](screenshots/desktop-quotation-award.png), [mobile award dialog](screenshots/mobile-quotation-award.png). They show actual practice screens. CI uploads the complete HTML report, traces on failures and screenshots.

## Isolation evidence and limits

The training launcher rejects inherited database URLs, production app environment, API URLs, integration destinations/tokens and secrets; it refuses operational `.env` files and unmarked nonempty data directories. Practice databases are generated only beneath the marked training directory. Python outbound socket operations, including loopback/DNS/UDP attempts, are denied in the actual training process. Cross-application service intake and delivery routes are disabled. Real posting services can create only local training outbox/notification records. No external worker is started. Tests verify configuration rejection before opening databases and inability to initiate outbound connections.

This is a guarantee within the maintained training entry point/configuration, not a claim that a machine administrator cannot modify code, replace executables or deliberately bypass the launcher. A hosted deployment still needs private access controls and its own environment verification.

## Corrective evaluation

A separate beginner-oriented pass checked terminology, missing steps, empty values, wrong quantities, interruptions and repeated attempts. It found and corrected: invalid synthetic email validation in the real account endpoint; guide advancement before backend posting completed; overlay overlap near right-edge buttons; mobile dialogs hidden behind the guide; report answers being checked before records loaded; location-planning responses overwriting a newer selection; blind quantities leaking through assessment evidence; old curriculum passes satisfying new prerequisites; task panels obstructing assisted work; zero-cost opening stock passing assessment; sign-out retaining the previous employee identity; Windows private event-loop initialization conflicting with the egress guard; and restart probes rejecting TIME_WAIT sockets. Regression checks cover these behaviors where applicable. This was an engineering evaluation, not an independent hospitality-employee usability study.

## Provisional quality audit

These are engineering judgments against the **entire master brief**, not predetermined scores or external certification.

| Category | Rating / 10 | Deficiency / next improvement |
|---|---:|---|
| Curriculum completeness | 6 | Catalogue/supplier mutations now work; food/property workflows, linked capstones and broader scenarios remain |
| Fidelity | 8 | Same current UI/services; live production comparison and remaining workflows still needed |
| Beginner friendliness | 8 | Short examples and correction work; test with actual first-time employees |
| Instruction clarity | 8 | Core tasks exercised; expand units, damaged/expired inspection details and decision variants |
| Guided practice | 8 | Visible targets, response waits and both viewports verified; remaining workflow controls need coverage |
| Scenario realism | 7 | Synthetic stock/PO/count/yield outcomes are real; linked days and wider item variety remain |
| Error recovery | 8 | Reset, saved-count resume, stale tabs and preserved history work; cross-device recovery and remaining unposted form drafts remain |
| Role relevance | 8 | Real roles/scopes enforced; fuller department paths and simultaneous assignments remain |
| Assessment quality | 6 | Real outcomes gate posting skills; expand multi-objective judgment tasks and calibrate role exams |
| Desktop usability | 8 | Automated workflows pass; independent human review still needed |
| Mobile usability | 8 | Pixel 7 emulation passes; real phones, other browsers and networks remain |
| Accessibility | 8 | Targeted axe/keyboard controls; full inherited-screen and assistive-technology audits remain |
| Isolation/safety | 9 | Fail-closed config, per-attempt DBs, masking and egress tests; native/hosted environment checks still needed |
| Maintainability | 8 | Typed lessons, separate fixtures/validators and drift gates; reusable registry migration/version tooling can improve |
| Automated testing | 8 | 195 training + 178 browser checks; all variants, full PostgreSQL and linked capstones remain |
| Deployment reliability | 5 | Standalone web build verified; actual private hosting, employee installation validation and signed distribution remain |

The final commit SHA and pull request URL are supplied in the delivery message/PR metadata. Completion, deployment and independent fidelity certification are deliberately not claimed.

# Inventory Training installation and operation

This is a separate application. Do not reuse the operational Inventory checkout, environment file, database, service unit, hostname, integration keys or deployment workflow. Training refuses inherited operational configuration and any adjacent `.env`. No production deployment has been performed.

## Employee access

Employees open the training link supplied by their trainer, enter their name, and select the work they were assigned. Continue Training restores their saved attempt. They need no Docker, database setup, API address or developer tools. Training uses fictional records; passing a path does not grant production permissions.

For a prepared desktop distribution, open **Hidden Oasis Inventory Training**. The launcher starts a local API and web server and opens the course. Keep the application running while training. If startup fails, the trainer can inspect `launcher-error.log` in the marked private training data folder. Return in the same browser profile to retain the participant session. Use **Sign out for another employee** before handing over a shared device. Sign-out preserves trainer history but removes the browser resume identity. Clearing browser cookies also loses the self-service resume identity; a trainer must recover records from the private training state. Cross-device authenticated identity is not implemented.

macOS builds are unsigned/ad-hoc, not Developer ID signed or notarized. Windows builds require the Windows CI result before distribution. Do not instruct employees to disable OS security controls. A private browser deployment is the alternative for managed devices; it still requires a separately provisioned host and access protection.

## Administrator source installation

Use a fresh checkout of the feature branch without `.env`. Install Python 3.12 and Node 22 using the organization's normal software distribution. The commands below are for the administrator preparing the package, not employees.

```sh
python3.12 -m venv .venv-training
.venv-training/bin/pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
bash scripts/package-inventory-training.sh
.venv-training/bin/python scripts/start-inventory-training.py
```

On Windows, use `.venv-training\Scripts\python.exe` and `.venv-training\Scripts\pip.exe`, build with `NEXT_PUBLIC_INVENTORY_TRAINING=1`, copy `.next/static` into `.next/standalone/.next/static`, then run `node scripts/verify-training-web.mjs`. The platform build workflow automates these steps and bundles Python and a checksum-verified official Node 22.23.5 runtime into the employee distribution.

The packaged frontend must contain `inventory-training-build.json`, produced only after verifying the compiled proxy and home route. The launcher refuses an unverified web payload. `scripts/build-inventory-training-desktop.py` produces a native unsigned build on the current platform; it cannot cross-compile a Windows executable from macOS. `.github/workflows/inventory-training-desktop.yml` builds on both platforms and checks the frozen API before uploading artifacts. An uploaded artifact is not proof that a real employee completed installation or that OS security warnings are resolved.

## Isolated runtime

- Frontend: `http://127.0.0.1:3400/training`.
- Backend: `127.0.0.1:8400`, with outbound Python socket connections denied, including loopback.
- Data: `%LOCALAPPDATA%/HiddenOasis/inventory-training` on Windows; `~/.local/share/HiddenOasis/inventory-training` on macOS/source installs.
- `progress.sqlite` retains learners, immutable attempt history, hints, mistakes and checkpoints. Registry schemas 1–3 migrate transactionally to schema 4, retaining curriculum versions, duty assignments, final records and answer-draft revisions. Legacy attempts remain history and do not satisfy current-version prerequisites.
- `attempt-<uuid>.sqlite` is a separate complete Inventory schema for each practice attempt. A reset creates a fresh file and preserves the previous one and its audit history. The current application models create these disposable schemas; existing attempt schemas are not upgraded in place. Source drift requires review and a new attempt/curriculum version.
- `session-key` signs participant cookies. `manager-key` protects cross-employee progress and assignments. Both are generated locally, must stay private, and must never enter a package, repository or screenshot.
- `web-runtime-<build>` is a writable per-build copy of the bundled web server. Next route caches stay here so using training cannot change the signed application bundle. It is disposable while training is stopped; learner records remain in the registry and attempt databases.

The trainer access code is the local `manager-key` value. An authorized administrator supplies it privately to the trainer. The employee role chooser, including Owner, cannot access the roster without that key. No actual staff messages, Accounting delivery or POS service intake is enabled.

Use the stopped-process [training recovery procedure](RECOVERY.md). It preserves the registry, every practice database and both private keys; it verifies a separate restored session, original stock transaction and frozen certificate. Disposable web caches are recreated from the application package. There is no production restore procedure in this training release.

## Separate private browser deployment

Provision a new host/service account and directory for training. Install only the built training web payload and backend source/runtime. Start `python -m training.launch --data /srv/hidden-oasis/inventory-training` from the separate backend directory and start the standalone Node server on loopback port 3400. Do not copy the production environment file. Set `INVENTORY_TRAINING_ORIGIN=https://inventory-training.hiddenoasis.app` only for this dedicated HTTPS deployment; it enables that exact origin and secure cookies. Other public origins, including production Inventory, are rejected.

Put an authenticated private TLS reverse proxy in front of loopback 3400. Use a dedicated DNS record, certificate, service units, backups and access rules. Do not enable an integration worker. Verify new-user onboarding, role/location restrictions, session recovery and no outbound delivery on that actual host before making it available. Emulated mobile viewports are tested against the source web app and macOS package; a real phone/network walkthrough remains required. No such deployment has been provisioned or verified in this change.

## Maintainer verification

```sh
cd backend
python -m training.validate
python -m pytest training/tests --confcutdir=training/tests -v
python -m pytest tests -q
cd ../frontend
npm run typecheck
NEXT_PUBLIC_INVENTORY_TRAINING=1 npm run build
npx playwright install chromium
npx playwright test --config playwright.training.config.ts
```

Run the API and training frontend on 8400/3400 before Playwright. The dedicated CI starts both, uploads screenshots/traces and packages the standalone web payload. Normal Inventory CI remains separate. The contract gate fingerprints backend logic and operational frontend sources; any change requires reviewing lesson routes, targets, role boundaries and expected outcomes before deliberately refreshing `source-contract.json`.

## Adding a lesson

Add a typed `Lesson` in `backend/training/curriculum.py` with a real route, actual supported roles, natural instructions, a worked example, correction and knowledge check. Add deterministic fixture preparation and a read-only outcome assertion in `scenarios.py`. Use explicit `{fixture_key}` value references; unbraced values are literal options. Do not infer variables from option names. For a newly created UUID record, a step outcome may match one UUID segment with `*`; resume must resolve the actual record route from committed business state. Add stable `data-training` attributes without changing workflow behavior. For posting/saving steps, specify `outcome` so the guide waits for the successful real API response. Test wrong input, post-result integrity, reset/resume and both viewports. Add a new curriculum version when completion contracts change. Update the coverage matrix and keep remaining work explicit.

During connected-work exercises, an exact POST-only allowlist permits the real database-only Operations decision and Accounting requeue handlers. The exception is task-scoped; service intake, publication, event processing and all transport workers remain disabled. The source contract gate and network guard still apply. These exercises can produce local pending handoffs, never a delivery or posted-journal claim.

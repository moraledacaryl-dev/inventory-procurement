# Recovering isolated Inventory Training

This procedure is for the qualified training administrator. Employees use Continue Training or ask the trainer for help. They do not need a terminal, Python or database tools.

The recovery copy contains employee names, learning history and private participant/trainer keys. Keep it in administrator-controlled private storage. Do not attach it to a PR, share it with employees or put it in a distribution package.

## Make a recovery copy

1. Close Inventory Training and stop its two local services. Keep the original data directory intact.
2. Choose a new recovery archive outside that directory. Existing archives are refused.
3. Run the appropriate prepared administrator command below. The command refuses occupied training ports, unmarked directories, missing practice databases, invalid SQLite relationships, incomplete keys, symlinks and state that changes during the copy.
4. Retain its SHA-256 with the archive. Rehearse a restore into a separate installation before relying on the copy.

For a source installation, from `backend`, using its installed Python 3.12 runtime:

```sh
python -m training.recovery backup --training-is-stopped --data /private/training/inventory-training --archive /private/recovery/training-recovery.zip
```

For a native macOS build, an administrator can invoke the bundled runtime directly, substituting their actual installation and private paths:

```sh
'/Applications/Hidden Oasis Inventory Training.app/Contents/MacOS/Hidden Oasis Inventory Training' --training-recovery backup --training-is-stopped --data "$HOME/.local/share/HiddenOasis/inventory-training" --archive /private/recovery/training-recovery.zip
```

For the native Windows build, from the extracted package in PowerShell:

```powershell
& '.\Hidden Oasis Inventory Training.exe' --training-recovery backup --training-is-stopped --data "$env:LOCALAPPDATA\HiddenOasis\inventory-training" --archive 'D:\PrivateRecovery\training-recovery.zip'
```

Native command dispatch is included in the build; its platform-specific proof belongs to the matching native workflow. A source drill alone does not verify a Windows installation. The command itself is not an employee onboarding step.

## Restore and verify

1. Stop training. Preserve the current directory under a separate administrator-controlled name; never overwrite it or merge databases.
2. Use the same application version initially. Choose an **absent** destination named `inventory-training`, under a separate private parent for the rehearsal.
3. Run `restore` with the archive and destination:

```sh
python -m training.recovery restore --training-is-stopped --archive /private/recovery/training-recovery.zip --data /private/rehearsal/inventory-training
```

The native command uses the same arguments after `--training-recovery`. Restoration verifies the manifest, exact permitted filenames, per-file checksums, SQLite integrity, database relationships and every saved attempt reference before exposing the directory. It refuses an existing destination. Earlier recovery copies remain untouched.

4. Start an isolated installation using the restored directory. Confirm the participant's identity, original transaction, attempt history, last checkpoint, completed final results and certificate. The source launcher accepts `--data`; a native launcher uses its documented private profile location. Rehearse on an isolated OS profile or test machine when preserving a live native installation.
5. Keep both the original and verified recovery copy until the trainer confirms the restored evidence. Per-build `web-runtime-*` caches are recreated from the verified application package; they are not learner evidence and are deliberately omitted.

`training/tests/test_recovery.py` performs a genuine stopped-process drill: an employee posts a 5 kg issue, completes three learning modes, passes a fresh module final and duty final, then the process exits. A new process opens a separate restored directory using the original signed cookies. It verifies the same participant, six retained attempts, frozen final/certificate and original single stock issue with 19 kg remaining. Tampered archives and unexpected paths are refused. POSIX file permissions are checked.

No production database is opened and no `BackupRecord` is manufactured. This verifies recovery of **training state**, not production Inventory backup readiness. The inherited assurance screen correctly continues to report no completed business backup record.

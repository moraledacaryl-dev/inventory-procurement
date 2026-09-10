import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.cwd(), 'visual-artifacts');
if (!fs.existsSync(root)) process.exit(0);

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

const manifests = walk(root).filter(file => file.endsWith(`${path.sep}manifest.json`));
const overall = { manifests: manifests.length, captures: 0, expectedAccessDenied: 0, unexpectedConsoleErrors: [], pageErrors: [] };

for (const file of manifests) {
  const rows = JSON.parse(fs.readFileSync(file, 'utf8'));
  for (const row of rows) {
    const errors = Array.isArray(row.consoleErrors) ? row.consoleErrors : [];
    const permissionErrors = errors.filter(message => /403 \(Forbidden\)/i.test(message));
    const unexpected = errors.filter(message => !/403 \(Forbidden\)/i.test(message));
    const expectedAccessDenied = row.role !== 'owner' && permissionErrors.length > 0;
    row.expectedAccessDenied = expectedAccessDenied;
    if (expectedAccessDenied) {
      row.state = 'expected-access-denied';
      row.consoleErrors = unexpected;
      overall.expectedAccessDenied += 1;
    }
    overall.captures += 1;
    overall.unexpectedConsoleErrors.push(...unexpected.map(error => `${row.project}/${row.role} ${row.route}: ${error}`));
    overall.pageErrors.push(...(row.pageErrors || []).map(error => `${row.project}/${row.role} ${row.route}: ${error}`));
  }
  fs.writeFileSync(file, JSON.stringify(rows, null, 2));
}

fs.writeFileSync(path.join(root, 'summary.json'), JSON.stringify(overall, null, 2));
console.log(JSON.stringify(overall, null, 2));
if (overall.pageErrors.length) process.exitCode = 1;

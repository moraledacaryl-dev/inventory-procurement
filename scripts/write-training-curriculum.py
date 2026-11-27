"""Refresh the reviewable lesson/role matrix from the versioned definitions."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from training.curriculum import LESSONS,ROLES,VERSION
from training.paths import PATHS

lines=['# Inventory Training curriculum and role matrix','',f'Curriculum version: `{VERSION}`. Generated from the typed definitions; review alongside source-contract.json and ENDPOINT_COVERAGE.md.','',
       'Each row is one definition with guided, assisted and independent variants. Item/quantity variants do not create additional unique business workflows. A check mark means the real source role is assigned the lesson; production location and monetary limits still apply.','',
       '| Module | Lesson ID and title | Manager | Purchasing | Receiver | Counter | Viewer | Owner | Evidence |',
       '|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|']
for lesson in sorted(LESSONS,key=lambda row:(row.module,row.id)):
    marks=['✓' if role in lesson.roles else '' for role in ROLES]
    evidence='Source record inspection' if lesson.workflow.startswith('read_') else 'Source protective refusal' if lesson.steps and lesson.steps[-1].outcome_status else 'Source business/master outcome'
    if lesson.workflow.startswith('capstone_'):evidence='Linked source outcomes in one database'
    lines.append('| '+ ' | '.join([lesson.module,f'`{lesson.id}` — {lesson.title}',*marks,evidence])+' |')
lines+=['','## Duty courses','', '| Course | Source role | Assigned definitions | Fresh duty-final tasks |','|---|---|---:|---|']
for path in PATHS:lines.append(f'| {path.title} (`{path.id}`) | `{path.role}` | {len(path.lessons)} | '+', '.join(f'`{id}`' for id in path.final_tasks)+' |')
lines+=['','Viewer reviews use the actual permitted reporting endpoints. Integration writes require separately authorized owner responsibility. Neither a training path, synthetic counterpart nor certificate grants production authority.','']
(ROOT/'docs/training/CURRICULUM.md').write_text('\n'.join(lines))

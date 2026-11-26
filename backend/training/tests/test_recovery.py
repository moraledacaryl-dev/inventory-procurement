"""Actual stopped-process drill preserves business, assessment and session evidence."""
import os
from pathlib import Path
import subprocess
import sys
import json
import zipfile
import pytest
from training.recovery import backup,restore

DRILL_CODE='from pathlib import Path\nfrom fastapi.testclient import TestClient\nfrom training.main import create_training_app\nfrom training.paths import BY_PATH,DutyPath\nfrom training.exams import blueprint\nimport json,sys,sqlite3\nroot=Path(sys.argv[1]);proof=Path(sys.argv[2]);phase=sys.argv[3]\npath=DutyPath(\'recovery-review\',\'Recovery review\',\'viewer\',\'A real bounded review used only in this drill.\',(\'available-stock\',),(\'available-stock\',))\nBY_PATH[path.id]=path\napp=create_training_app(root,guard_network=False)\nclient=TestClient(app);client.headers[\'X-Requested-With\']=\'HiddenOasisInventory\'\ndef post(url,payload):\n    response=client.post(\'/api/v1\'+url,json=payload)\n    assert response.status_code in {200,201},response.text\n    return response.json()\nif phase==\'prepare\':\n    post(\'/training/enrol\',{\'name\':\'Fictional recovery employee\',\'role\':\'inventory_manager\'})\n    started=post(\'/training/start\',{\'lesson_id\':\'issue-kitchen\'});client.headers[\'X-Training-Attempt\']=started[\'attempt_id\']\n    issue=post(\'/stock/issues\',{\'location_id\':\'training-store\',\'reference\':\'TRAIN-RECOVERY-ISSUE\',\'lines\':[{\'item_id\':\'training-chicken\',\'quantity\':5}]})\n    assert post(\'/training/check\',{\'answer\':\'issue\'})[\'passed\']\n    business_attempt=started[\'attempt_id\']\n    post(\'/training/enrol\',{\'name\':\'Fictional recovery employee\',\'role\':\'viewer\',\'path_id\':path.id})\n    def task(mode,exam=None):\n        started=post(\'/training/start\',{\'lesson_id\':\'available-stock\',\'mode\':mode,\'exam_id\':exam});client.headers[\'X-Training-Attempt\']=started[\'attempt_id\']\n        assert client.get(\'/api/v1/availability\').status_code==200\n        assert post(\'/training/check\',{\'answer\':\'available\',\'observation\':{\'guided\':\'20\',\'assisted\':\'23\',\'independent\':\'27\'}[mode]})[\'passed\']\n    for mode in (\'guided\',\'assisted\',\'independent\'):task(mode)\n    for module in (\'A\',None):\n        exam=post(\'/training/exams/start\',{\'module\':module});task(\'independent\',exam[\'id\'])\n        row=blueprint(path.id,module)\n        result=post(\'/training/exams/\'+exam[\'id\']+\'/submit\',{\'answers\':{q.id:q.answer for q in row[\'questions\']}})\n        assert result[\'status\']==\'passed\'\n    profile=client.get(\'/api/v1/training/me\').json()\n    proof.write_text(json.dumps({\'cookies\':dict(client.cookies),\'profile\':profile,\'exam\':result,\'business_attempt\':business_attempt,\'document\':issue,\'binding\':client.headers[\'X-Training-Attempt\']}));proof.chmod(0o600)\nelse:\n    saved=json.loads(proof.read_text());client.cookies.update(saved[\'cookies\']);client.headers[\'X-Training-Attempt\']=saved[\'binding\']\n    profile=client.get(\'/api/v1/training/me\');assert profile.status_code==200,profile.text\n    profile=profile.json()\n    assert profile[\'learner\']==saved[\'profile\'][\'learner\']\n    assert profile[\'history\']==saved[\'profile\'][\'history\']\n    exam=client.get(\'/api/v1/training/exams/\'+saved[\'exam\'][\'id\']);assert exam.status_code==200,exam.text\n    assert exam.json()[\'result\']==saved[\'exam\'][\'result\']\n    assert exam.json()[\'result\'][\'certificate\']\n    with sqlite3.connect(root/(\'attempt-\'+saved[\'business_attempt\']+\'.sqlite\')) as db:\n        assert db.execute("SELECT quantity FROM stock_balances WHERE item_id=\'training-chicken\' AND location_id=\'training-store\'").fetchone()[0]==19\n        assert db.execute("SELECT count(*) FROM stock_documents WHERE reference=\'TRAIN-RECOVERY-ISSUE\'").fetchone()[0]==1\n        assert db.execute("SELECT count(*) FROM stock_movements WHERE document_id=?",(saved[\'document\'][\'id\'],)).fetchone()[0]==1\n    print(json.dumps({\'restored_history\':len(profile[\'history\']),\'certified\':True,\'original_issue_preserved\':True,\'original_session_restored\':True}))\n'


def test_stopped_recovery_retains_original_transaction_history_final_grade_and_cookie(tmp_path):
    original=tmp_path/"original"/"inventory-training";proof=tmp_path/"private-drill-proof.json"
    env={key:value for key,value in os.environ.items() if key not in {"DATABASE_URL","JWT_SECRET","BOOTSTRAP_OWNER_PASSWORD","INTERNAL_API_URL","NEXT_PUBLIC_API_URL"} and "INTEGRATION" not in key}
    env["APP_ENV"]="training"
    prepared=subprocess.run([sys.executable,"-c",DRILL_CODE,str(original),str(proof),"prepare"],capture_output=True,text=True,env=env)
    assert prepared.returncode==0,prepared.stderr
    archive=tmp_path/"private-training-recovery.zip"
    (original/"web-runtime-disposable").mkdir();(original/"web-runtime-disposable"/"server.js").write_text("recreated from verified package")
    with pytest.raises(ValueError,match="Stop training"):backup(original,archive)
    backed=backup(original,archive,stopped=True)
    restored=tmp_path/"recovered"/"inventory-training"
    result=restore(archive,restored,stopped=True)
    assert backed==result
    assert not (restored/"web-runtime-disposable").exists()
    assert (restored/"session-key").read_bytes()==(original/"session-key").read_bytes()
    assert (restored/"manager-key").read_bytes()==(original/"manager-key").read_bytes()
    verified=subprocess.run([sys.executable,"-c",DRILL_CODE,str(restored),str(proof),"verify"],capture_output=True,text=True,env=env)
    assert verified.returncode==0,verified.stderr
    assert json.loads(verified.stdout)=={"restored_history":6,"certified":True,"original_issue_preserved":True,"original_session_restored":True}
    with pytest.raises(ValueError,match="new private backup"):backup(original,archive,stopped=True)
    with pytest.raises(ValueError,match="new, absent"):restore(archive,restored,stopped=True)
    if os.name=="posix":
        assert archive.stat().st_mode&0o777==0o600
        assert restored.stat().st_mode&0o777==0o700
        assert (restored/"session-key").stat().st_mode&0o777==0o600
    # Neither source nor restored evidence pretends a production backup ran.
    import sqlite3
    for root in (original,restored):
        attempt=next(root.glob("attempt-*.sqlite"))
        with sqlite3.connect(attempt) as db:assert db.execute("SELECT count(*) FROM backup_records").fetchone()[0]==0
    # Tampering, unexpected paths and partial backups never create a target.
    bad=tmp_path/"tampered.zip"
    with zipfile.ZipFile(archive) as source,zipfile.ZipFile(bad,"w") as out:
        for name in source.namelist():out.writestr(name,b"changed" if name=="session-key" else source.read(name))
    target=tmp_path/"tampered"/"inventory-training"
    with pytest.raises(ValueError,match="checksum"):restore(bad,target,stopped=True)
    assert not target.exists()
    malicious=tmp_path/"unexpected.zip"
    with zipfile.ZipFile(malicious,"w") as out:
        out.writestr("recovery-manifest.json",json.dumps({"format":"hidden-oasis-training-recovery-v1","files":{"../session-key":"fake"}}));out.writestr("../session-key","bad")
    with pytest.raises(ValueError,match="unexpected path"):restore(malicious,target,stopped=True)
    assert not target.exists()

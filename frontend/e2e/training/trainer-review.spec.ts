import {expect,test} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {certifyViewerViaRealApis,readPractice,knowledge,requestHeaders} from './assessment-helpers';

test.use({trace:'off'}); // Keep the private local trainer key out of traces.

  test('the trainer sees current duty certification and retained practical history',async({page},info)=>{
    const keyPath=process.env.TRAINING_MANAGER_KEY_PATH;
    expect(keyPath,'The verified launcher must provide its private test key path').toBeTruthy();
    const {identity}=await certifyViewerViaRealApis(page,'Fictional trainer-review colleague');
    const started=await page.request.post('/api/v1/training/exams/start',{headers:requestHeaders,data:{}});expect(started.ok(),await started.text()).toBeTruthy();const exam=await started.json();
    for(const id of exam.blueprint.practical_lessons)await readPractice(page,id,'independent',exam.id);
    const passed=await page.request.post(`/api/v1/training/exams/${exam.id}/submit`,{headers:requestHeaders,data:{answers:knowledge(exam.blueprint)}});expect((await passed.json()).status).toBe('passed');
    await page.goto('/training/management');await page.getByLabel('Trainer access code',{exact:true}).fill(readFileSync(keyPath!,'utf8').trim());
    await page.getByRole('button',{name:'Open training progress',exact:true}).click();await page.getByRole('combobox',{name:'Employee to review',exact:true}).selectOption(identity.id);
    await expect(page.getByText('Current duty final passed',{exact:false})).toBeVisible();
    await expect(page.getByRole('cell',{name:`TRAINING-${exam.id}`,exact:true})).toBeVisible();
    await page.screenshot({path:`training-test-results/${info.project.name}-trainer-final-review.png`,fullPage:true});
  });
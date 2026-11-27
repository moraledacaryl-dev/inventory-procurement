import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type {TrainingCatalogue} from '../../lib/inventory-training';
import type {ExamBlueprint,ExamRecord} from '../../lib/training-exams';
import {enrol,study,performReadInBrowser,fillKnowledge,certifyViewerViaRealApis,knowledge} from './assessment-helpers';

for(const path_id of ['stockroom','kitchen','cafe','bar','housekeeping','maintenance','department-supervisor','accounting-review','role-inventory_manager','role-procurement_officer','role-receiver','role-counter','role-viewer','role-owner']){
  test(`an employee opens the actual ${path_id} duty course`,async({page})=>{
    await page.goto('/training');
    await page.getByLabel('Your name',{exact:true}).fill('Fictional duty colleague');
    await page.getByRole('combobox',{name:'Your training responsibilities',exact:true}).selectOption(path_id);
    await page.getByRole('button',{name:'Start training',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Welcome back, Fictional duty colleague.',exact:true})).toBeVisible();
    const profile=await(await page.request.get('/api/v1/training/me')).json();
    const catalogue=await(await page.request.get('/api/v1/training/catalogue')).json() as TrainingCatalogue;
    const path=catalogue.paths.find(path=>path.id===path_id)!;
    expect(profile.learner.path_id).toBe(path.id);expect(profile.learner.role).toBe(path.role);
    await expect(page.locator('.training-overview .training-eyebrow')).toHaveText(path.title);
    await expect(page.locator('.training-lessons article')).toHaveCount(path.lessons.length);
    await page.getByRole('button',{name:'Continue training →',exact:true}).click();
    await expect(page.getByRole('dialog',{name:'Lesson overview'})).toBeVisible();
    await expect(page.getByRole('button',{name:'Start guided practice',exact:true})).toBeEnabled();
  });
}

test('shared skills and multiple duty assignments survive changing courses',async({page},info)=>{
  const {catalogue}=await enrol(page,'Fictional multi-duty colleague','housekeeping');await study(page,['available-stock']);
  const housekeeping=catalogue.paths.find(path=>path.id==='housekeeping')!.lessons.length;
  const kitchen=catalogue.paths.find(path=>path.id==='kitchen')!.lessons.length;
  await page.goto('/training');
  await expect(page.locator('.training-progress strong')).toHaveText(`1 / ${housekeeping}`);
  await page.locator('summary').filter({hasText:'Practise another training path'}).click();
  await page.getByRole('combobox',{name:'Responsibilities',exact:true}).selectOption('kitchen');
  await page.getByRole('button',{name:'Use this training path',exact:true}).click();
  await expect(page.locator('.training-overview .training-eyebrow')).toHaveText('Kitchen preparation');
  await expect(page.locator('.training-progress strong')).toHaveText(`1 / ${kitchen}`);
  await page.getByRole('button',{name:`Housekeeping and linen · 1/${housekeeping}`,exact:true}).click();
  await expect(page.locator('.training-overview .training-eyebrow')).toHaveText('Housekeeping and linen');
  await expect(page.locator('.training-progress strong')).toHaveText(`1 / ${housekeeping}`);
  await page.screenshot({path:`training-test-results/${info.project.name}-multiple-duty-courses.png`,fullPage:true});
});

test('a module final saves answers, refuses a critical error and retains a fresh retake',async({page},info)=>{
  await enrol(page);await study(page,['available-stock']);await page.goto('/training/assessments');
  const moduleEntry=page.locator('.training-exam-entry').filter({has:page.getByRole('heading',{name:'Module A final',exact:true})});
  await moduleEntry.getByRole('button',{name:'Start final check',exact:true}).click();
  await expect(page).toHaveURL(/assessments\?exam=/);
  const initial=new URL(page.url()).searchParams.get('exam')!;
  await page.getByRole('button',{name:'Start fresh independent task',exact:true}).click();
  await performReadInBrowser(page,'available-stock');
  const row=(await(await page.request.get(`/api/v1/training/exams/${initial}`)).json()).blueprint as ExamBlueprint;
  const saved=page.waitForResponse(response=>response.url().endsWith(`/exams/${initial}/draft`)&&response.status()===200);
  await fillKnowledge(page,{...knowledge(row),unit:'250'});await saved;
  await expect(page.getByRole('status')).toHaveText('Answers saved');await page.reload();
  await expect(page.locator('[data-training-question="unit"]')).toHaveValue('250');
  await page.getByRole('button',{name:'Submit final check',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Practise these points, then try a fresh final',exact:true})).toBeVisible();
  await expect(page.getByText('85.71% · needs 85%',{exact:true})).toBeVisible();
  await expect(page.getByText('A required check needs correction',{exact:true})).toBeVisible();
  await expect(page.getByText('1,000 g is 1 kg, so 250 g is 0.25 kg.',{exact:true})).toBeVisible();
  await page.screenshot({path:`training-test-results/${info.project.name}-critical-final-correction.png`,fullPage:true});
  await page.getByRole('button',{name:'Start a fresh retake',exact:true}).click();
  await expect(page).not.toHaveURL(new RegExp(initial));
  const fresh=new URL(page.url()).searchParams.get('exam')!;expect(fresh).not.toBe(initial);
  await expect(page.getByRole('button',{name:'Submit final check',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Start fresh independent task',exact:true}).click();await performReadInBrowser(page,'available-stock');
  await fillKnowledge(page,{...knowledge(row),value:'400'});await page.getByRole('button',{name:'Submit final check',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Final check passed',exact:true})).toBeVisible();
  await expect(page.getByText('85.71% · needs 85%',{exact:true})).toBeVisible();
  const history=(await(await page.request.get('/api/v1/training/exams')).json()).history as ExamRecord[];
  expect(history.find(exam=>exam.id===initial)?.status).toBe('failed');expect(history.find(exam=>exam.id===fresh)?.status).toBe('passed');
});

test('the duty final requires fresh actual inspections and issues a training-only result',async({page},info)=>{
  await certifyViewerViaRealApis(page,'Fictional certified reviewer');await page.goto('/training/assessments');
  const course=page.locator('.training-exam-entry').filter({has:page.getByRole('heading',{name:'Reports and review final',exact:true})});
  await course.getByRole('button',{name:'Start final check',exact:true}).click();
  for(const id of ['available-stock','management-review']){
    // Resolve the actual title from the public definition rather than assuming
    // it stays identical when the source curriculum is reviewed.
    const catalogue=await(await page.request.get('/api/v1/training/catalogue')).json() as TrainingCatalogue;
    const title=catalogue.lessons.find(lesson=>lesson.id===id)!.title;
    await page.locator('.training-exam-task').filter({has:page.getByRole('heading',{name:title,exact:true})}).getByRole('button',{name:'Start fresh independent task',exact:true}).click();
    await performReadInBrowser(page,id);
  }
  const examId=new URL(page.url()).searchParams.get('exam')!;
  const row=(await(await page.request.get(`/api/v1/training/exams/${examId}`)).json()).blueprint as ExamBlueprint;
  await fillKnowledge(page,knowledge(row));await page.getByRole('button',{name:'Submit final check',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Final check passed',exact:true})).toBeVisible();
  await expect(page.getByText(`TRAINING-${examId}`,{exact:true})).toBeVisible();
  await expect(page.getByText('This is your training record. Your manager assigns production access separately.',{exact:false})).toBeVisible();
  await page.screenshot({path:`training-test-results/${info.project.name}-duty-final-certificate.png`,fullPage:true});
});

test('the new final-check page has no serious accessibility violations',async({page})=>{
  await enrol(page);await study(page,['available-stock']);await page.goto('/training/assessments');
  await page.locator('.training-exam-entry').filter({has:page.getByRole('heading',{name:'Module A final',exact:true})}).getByRole('button',{name:'Start final check',exact:true}).click();
  await expect(page.locator('[data-training-question="unit"]')).toBeVisible();
  const result=await new AxeBuilder({page}).include('.training-exams').analyze();expect(result.violations.filter(violation=>['serious','critical'].includes(violation.impact||''))).toEqual([]);
});


test('quick reference answers a real question and opens authorized refresher practice',async({page},info)=>{
  await enrol(page,'Fictional refresher learner','role-owner');await page.goto('/training');
  await page.getByRole('button',{name:'Quick reference',exact:true}).click();
  await page.getByRole('searchbox',{name:'Find a lesson or situation',exact:true}).fill('incorrect receipt');
  const reference=page.getByRole('region',{name:'Practical reference'});
  await reference.locator('summary').filter({hasText:'How do I correct an incorrect receipt?'}).click();
  await expect(reference).toContainText('another receipt is not an undo button');
  await reference.getByRole('button',{name:'Review Return previously accepted goods',exact:true}).click();
  const lesson=page.getByRole('dialog',{name:'Lesson overview'});
  await expect(lesson.getByRole('heading',{name:'Return previously accepted goods',exact:true})).toBeVisible();
  await lesson.getByRole('button',{name:'← Back to your course',exact:true}).click();
  await page.getByRole('searchbox',{name:'Find a lesson or situation',exact:true}).fill('variance');
  await reference.locator('summary').filter({hasText:'Words used in Inventory'}).click();
  await expect(reference.getByText('The difference between the physical count and the stock balance recorded when counting began.',{exact:false})).toBeVisible();
  const result=await new AxeBuilder({page}).include('.training-reference').analyze();expect(result.violations.filter(violation=>['serious','critical'].includes(violation.impact||''))).toEqual([]);
  await page.screenshot({path:`training-test-results/${info.project.name}-quick-reference.png`});
});

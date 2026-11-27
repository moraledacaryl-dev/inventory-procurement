import {expect,type Page} from '@playwright/test';
import type {TrainingCatalogue,TrainingLesson} from '../../lib/inventory-training';
import type {ExamBlueprint} from '../../lib/training-exams';

export const requestHeaders={'X-Requested-With':'HiddenOasisInventory'};
const reading:Record<string,{answer:string;observations:string[]}>= {
  'available-stock':{answer:'available',observations:['20','23','27']},
  'find-your-work':{answer:'no',observations:['1','1','1']},
  'catalogue-units':{answer:'1000',observations:['1000','1000','1000']},
  'supplier-profile':{answer:'no',observations:['3','3','3']},
  'expiry-rotation':{answer:'no',observations:['5','6','7']},
  'recipe-cost':{answer:'1',observations:['50','50','50']},
  'accounting-proof':{answer:'no',observations:['ready for review','ready for review','ready for review']},
  'interpret-stock-valuation':{answer:'no',observations:['6000','6750','7750']},
  'interpret-period-issues':{answer:'no',observations:['-6','-5','-4']},
  'interpret-waste-value':{answer:'no',observations:['-1200','-1000','-800']},
  'interpret-posted-count':{answer:'no',observations:['-3','-7','-12']},
  'interpret-supplier-acceptance':{answer:'no',observations:['80','77.78','75']},
  'interpret-actual-yield-cost':{answer:'no',observations:['60','66.67','75']},
  'interpret-assurance-evidence':{answer:'no',observations:['failed','failed','failed']},
  'sale-consumption':{answer:'no',observations:['-340','-255','-170']},
  'inspect-pos-duplicate-delivery':{answer:'no',observations:['1','1','1']},
  'inspect-unmapped-pos-refusal':{answer:'no',observations:['0','0','0']},
  'inspect-cooked-sale-return':{answer:'no',observations:['3','3','3']},
  'inspect-unused-sale-void':{answer:'no',observations:['-170','-85','-85']},
  'management-review':{answer:'no',observations:['2000','2400','2800']},
};
const foundation={available:'20',unit:'0.25',value:'500',authority:'no'};
const topicAnswers:Record<string,string>={
  'A-physical':'no','A-movement':'yes','A-shortage':'2',
  'B-restricted':'no','B-location':'yes','B-history':'yes',
  'C-case':'72','C-conversion':'no','C-deactivate':'no',
  'I-terms':'no','I-preferred':'no','I-orders':'no',
  'O-expiry':'no','O-lot':'no','O-trace':'yes',
  'D-opening':'yes','D-cost':'no','D-duplicate':'no',
  'G-truth':'8','G-zero':'no','G-approval':'no',
  'H-waste':'yes','H-correction':'no','H-signed':'-3',
  'P-yield':'3','P-allowance':'0.275','P-approve':'no',
  'Q-plan':'no','Q-usable':'10','Q-actual':'no',
  'S-raw':'no','S-retry':'no','S-refund':'no',
  'W-delivery':'no','W-retry':'no','W-accepted':'no',
  'Y-cause':'no','Y-basis':'yes','Y-review':'no',
  'M-rejection':'no','T-reservation':'no',
  'final-A-physical':'no','final-Y-cause':'no','final-B-restricted':'no','final-C-case':'72','final-I-terms':'no',
  'final-G-truth':'8','final-M-accepted':'6','final-K-deadline':'1','final-S-raw':'no','final-W-delivery':'no',
};
export function knowledge(row:ExamBlueprint){return Object.fromEntries(row.questions.map(question=>[question.id,({...foundation,...topicAnswers} as Record<string,string>)[question.id]]))}
export async function enrol(page:Page,name='Fictional assessment learner',path_id='role-viewer'){
  const catalogue=await(await page.request.get('/api/v1/training/catalogue')).json() as TrainingCatalogue;
  const role=catalogue.paths.find(path=>path.id===path_id)!.role;
  const response=await page.request.post('/api/v1/training/enrol',{headers:requestHeaders,data:{name,role,path_id}});expect(response.ok(),await response.text()).toBeTruthy();
  return {identity:await response.json(),catalogue};
}
export async function readPractice(page:Page,id:string,mode='guided',exam_id?:string){
  const started=await page.request.post('/api/v1/training/start',{headers:requestHeaders,data:{lesson_id:id,mode,exam_id}});expect(started.ok(),await started.text()).toBeTruthy();
  const data=await started.json() as {attempt_id:string;lesson:TrainingLesson};
  const headers={...requestHeaders,'X-Training-Attempt':data.attempt_id};
  const profile=await(await page.request.get('/api/v1/training/me',{headers})).json();
  const params=profile.lesson.inspection_query||{};
  const record=await page.request.get(profile.lesson.inspection_api_path!,{headers,params});expect(record.ok(),await record.text()).toBeTruthy();
  const result=await page.request.post('/api/v1/training/check',{headers,data:{answer:reading[id].answer,observation:reading[id].observations[['guided','assisted','independent'].indexOf(mode)]}});expect(result.ok(),await result.text()).toBeTruthy();expect((await result.json()).passed).toBeTruthy();
  return data;
}
export async function study(page:Page,ids:string[]){for(const id of ids)for(const mode of ['guided','assisted','independent'])await readPractice(page,id,mode)}
export async function performReadInBrowser(page:Page,id:string){
  await expect(page).not.toHaveURL(/\/training\/assessments(?:\?|$)/);
  await expect(page.getByRole('complementary',{name:'Your training task'})).toBeVisible();
  const profile=await(await page.request.get('/api/v1/training/me')).json();
  const lesson=profile.lesson as TrainingLesson;
  expect(lesson.id).toBe(id);
  const coach=page.getByRole('complementary',{name:'Your training task'});
  await coach.getByRole('link',{name:'Open the record to inspect →',exact:true}).click();
  await coach.getByRole('textbox',{name:lesson.question,exact:true}).fill(reading[id].answer);
  await coach.getByRole('textbox',{name:lesson.practical_question,exact:true}).fill(reading[id].observations[2]);
  await coach.getByRole('button',{name:'Check my work',exact:true}).click();
  await expect(coach.getByRole('heading',{name:'Task passed',exact:true})).toBeVisible();
  await coach.getByRole('link',{name:'Continue your final check →',exact:true}).click();
  await expect(page.getByRole('heading',{name:'1. Perform the work',exact:true})).toBeVisible();
}
export async function fillKnowledge(page:Page,answers:Record<string,string>){for(const[id,value]of Object.entries(answers))await page.locator(`[data-training-question="${id}"]`).fill(value)}
export async function certifyViewerViaRealApis(page:Page,name:string){
  const {identity,catalogue}=await enrol(page,name);
  const path=catalogue.paths.find(path=>path.id==='role-viewer')!;
  await study(page,path.lessons);
  const finals=await(await page.request.get('/api/v1/training/exams')).json();
  for(const row of finals.blueprints.filter((row:ExamBlueprint)=>row.module)){
    const started=await page.request.post('/api/v1/training/exams/start',{headers:requestHeaders,data:{module:row.module}});expect(started.ok(),await started.text()).toBeTruthy();const exam=await started.json();
    for(const id of row.practical_lessons)await readPractice(page,id,'independent',exam.id);
    const passed=await page.request.post(`/api/v1/training/exams/${exam.id}/submit`,{headers:requestHeaders,data:{answers:knowledge(row)}});expect((await passed.json()).status).toBe('passed');
  }
  return {identity,catalogue};
}


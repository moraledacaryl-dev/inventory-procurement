export type TrainingStep = { target: string; instruction: string; value: string | number | null; event: string; outcome: string | null; outcome_status: number | null };
export type TrainingLesson = {
  id: string; module: string; title: string; roles: string[]; route: string;
  workflow: string; situation: string; concept: string; example: string; rule: string;
  question: string; correction: string; sources: string[]; steps: TrainingStep[];
  quantity: number; rejected: number; reference: string; practical_question: string; inspection_route: string;
  curriculum_version: string;
  inspection_api_path: string | null;
  global_access: boolean;
};
export type TrainingAttempt = {
  id: string; lesson_id: string; mode: "guided" | "assisted" | "independent";
  role: string; status: string; hints: number; mistakes: number; checkpoint: number;
  started_at: string; completed_at: string | null; evidence: string;
  curriculum_version: string; path_id:string; exam_id:string|null;
};
export type TrainingProfile = {
  learner: { id: string; name: string; role: string; path_id:string }; attempt: TrainingAttempt | null;
  lesson: TrainingLesson | null; history: TrainingAttempt[]; version: string;
  record_inspected: boolean; assignments:{path_id:string;created_at:string}[];
};
export type DutyPath = {id:string;title:string;role:string;description:string;lessons:string[];final_tasks:string[]};
export type TrainingCatalogue = { paths:DutyPath[]; version: string; roles: Record<string, string>; lessons: TrainingLesson[];
  capstones: { id: string; title: string; lessons: string[]; linked?:boolean }[]; environment: string };

export function mastery(history: TrainingAttempt[], lesson: TrainingLesson, role: string) {
  const modes = new Set(history.filter(row => row.lesson_id === lesson.id && row.role === role && row.status === "passed" && row.curriculum_version === lesson.curriculum_version).map(row => row.mode));
  return { guided: modes.has("guided"), assisted: modes.has("assisted"), independent: modes.has("independent") };
}

export const trainingEnabled = process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1";

export function trainingOutcomeMatches(expected:string,actual:string) {
  actual=actual.split("?")[0];
  if(!expected.includes("*"))return expected===actual;
  const parts=expected.split("*");
  if(parts.length!==2||!actual.startsWith(parts[0])||!actual.endsWith(parts[1]))return false;
  const id=actual.slice(parts[0].length,actual.length-parts[1].length);
  return /^[a-f0-9-]{36}$/.test(id);
}

export type TrainingStep = { target: string; instruction: string; value: string | number | null; event: string; outcome: string | null };
export type TrainingLesson = {
  id: string; module: string; title: string; roles: string[]; route: string;
  workflow: string; situation: string; concept: string; example: string; rule: string;
  question: string; correction: string; sources: string[]; steps: TrainingStep[];
  quantity: number; rejected: number; reference: string; practical_question: string; inspection_route: string;
  curriculum_version: string;
  inspection_api_path: string | null;
};
export type TrainingAttempt = {
  id: string; lesson_id: string; mode: "guided" | "assisted" | "independent";
  role: string; status: string; hints: number; mistakes: number; checkpoint: number;
  started_at: string; completed_at: string | null; evidence: string;
  curriculum_version: string;
};
export type TrainingProfile = {
  learner: { id: string; name: string; role: string }; attempt: TrainingAttempt | null;
  lesson: TrainingLesson | null; history: TrainingAttempt[]; version: string;
  record_inspected: boolean;
};
export type TrainingCatalogue = { version: string; roles: Record<string, string>; lessons: TrainingLesson[];
  capstones: { id: string; title: string; lessons: string[] }[]; environment: string };

export function mastery(history: TrainingAttempt[], lesson: TrainingLesson, role: string) {
  const modes = new Set(history.filter(row => row.lesson_id === lesson.id && row.role === role && row.status === "passed" && row.curriculum_version === lesson.curriculum_version).map(row => row.mode));
  return { guided: modes.has("guided"), assisted: modes.has("assisted"), independent: modes.has("independent") };
}

export const trainingEnabled = process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1";

import adminApi from './axios'

export type Discipline = 'snowboard' | 'ski'
export type Rating = 1 | 2 | 3
export const DISCIPLINES = {snowboard:'單板', ski:'雙板'} as const
export const RATINGS: Rating[] = [1, 2, 3]

export interface Skill { id: string; title: string }
export interface SkillSection { id: string; title: string; skills: Skill[] }
export interface SkillRule { level: number; match: 'any' | 'all'; criteria: {skill:string;rating:Rating}[] }
export interface DisciplineRubric { entry_level: number; sections: SkillSection[]; rules: SkillRule[] }
export interface AssessmentRubric { ratings: Record<Rating, string>; disciplines: Record<Discipline, DisciplineRubric> }
export interface RubricConfig { revision: string; rubric: AssessmentRubric; can_edit: boolean }
export interface SkillEntry { scores: Record<string, Rating>; next_steps: string[] }
export type SkillEntries = Partial<Record<Discipline, SkillEntry>>
export interface SkillSnapshot { revision: string; rubric: AssessmentRubric; entries: SkillEntries }

export async function fetchAssessmentRubric(coach: boolean): Promise<RubricConfig> {
  const {data} = await adminApi.get(coach ? '/coach/evaluations/rubric/' : '/evaluations/rubric/') as unknown as {data:RubricConfig}
  return data
}

export async function saveAssessmentRubric(revision: string, rubric: AssessmentRubric): Promise<RubricConfig> {
  const {data} = await adminApi.put('/evaluations/rubric/', {revision,rubric}) as unknown as {data:RubricConfig}
  return data
}

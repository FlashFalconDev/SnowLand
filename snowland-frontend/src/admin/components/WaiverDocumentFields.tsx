import type { PreCourseQuestion, SiteContentWriteData } from '../api/siteContent'

export default function WaiverDocumentFields({value,onChange}:{value:SiteContentWriteData;onChange:(patch:Partial<SiteContentWriteData>)=>void}) {
  const input='mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white'
  const questions = (Array.isArray(value.metadata?.questions) ? value.metadata.questions : []) as PreCourseQuestion[]
  const saveQuestions = (next: PreCourseQuestion[]) => onChange({metadata:{...value.metadata,questions:next}})
  const editQuestion = (key: string, patch: Partial<PreCourseQuestion>) =>
    saveQuestions(questions.map(question => question.key === key ? {...question,...patch} : question))
  return <section aria-label="聲明書內容與版本" className="space-y-4 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
    <h3 className="font-semibold text-gray-900 dark:text-white">聲明書內容與版本</h3>
    <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">修改標題、正文或題目會自動建立新版本。公開後，已簽舊版的會員需要重簽。原簽名與文件快照會保留，包含當時的題目與答案。</p>
    <p className="break-all text-xs text-gray-600 dark:text-gray-300">目前版本：{String(value.metadata?.version || '儲存時自動產生')}（不需自行編號）</p>
    <label className="block text-sm text-gray-700 dark:text-gray-200">聲明書標題<input required value={value.title} onChange={e=>onChange({title:e.target.value})} className={input}/></label>
    <label className="block text-sm text-gray-700 dark:text-gray-200">聲明書完整正文<textarea required rows={12} value={value.body} onChange={e=>onChange({body:e.target.value})} className={input}/></label>
    <h4 className="font-semibold">自訂課前題目</h4>
    {questions.map((question, index) => <fieldset key={question.key} className="space-y-3 rounded-lg border p-3">
      <legend className="px-1 text-sm font-semibold">第 {index + 1} 題</legend>
      <label className="block text-sm">題目文字<input required maxLength={250} value={question.title} className={input}
        onChange={event => editQuestion(question.key,{title:event.target.value})} /></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">顯示區塊<select value={question.section} className={input}
          onChange={event => editQuestion(question.key,{section:event.target.value as PreCourseQuestion['section']})}>
          <option value="insurance">保險資料</option><option value="waiver">課前聲明書</option>
        </select></label>
        <label className="block text-sm">題型<select value={question.kind} className={input}
          onChange={event => editQuestion(question.key,{kind:event.target.value as PreCourseQuestion['kind']})}>
          <option value="text">文字填寫</option><option value="single">單選</option><option value="multiple">複選</option>
        </select></label>
      </div>
      {question.kind !== 'text' && <label className="block text-sm">選項（每行一個）<textarea required rows={3}
        value={question.options.join('\n')} className={input}
        onChange={event => editQuestion(question.key,{options:event.target.value.split('\n')})} /></label>}
      <div className="flex items-center justify-between">
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={question.required}
          onChange={event => editQuestion(question.key,{required:event.target.checked})} />必填</label>
        <button type="button" className="min-h-11 text-sm text-red-700 dark:text-red-300"
          onClick={() => saveQuestions(questions.filter(row => row.key !== question.key))}>移除這題</button>
      </div>
    </fieldset>)}
    <button type="button" className="min-h-11 rounded-lg border px-4 text-sm disabled:opacity-50" disabled={questions.length >= 24}
      onClick={() => saveQuestions([...questions,{key:crypto.randomUUID(),title:'',section:'waiver',kind:'text',required:false,options:[]}])}>新增題目</button>
    <label className="flex min-h-11 items-start gap-3 text-sm leading-6 text-gray-700 dark:text-gray-200"><input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={Boolean(value.metadata?.is_draft)} onChange={e=>onChange({metadata:{...value.metadata,is_draft:e.target.checked}})}/>文件仍待法務確認（會員端會顯示提示）</label>
    <p className="text-xs leading-6 text-gray-500 dark:text-gray-400">上方「草稿」只保存、不公開；選擇「進行中」後儲存，才會成為會員使用的文件。此處不會代會員簽署。</p>
  </section>
}

import { useId } from 'react'
import { recruitmentFileFormats, type RecruitmentField } from './recruitmentForm'

const inputClass = 'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-[#2b5f8f] focus:outline-none focus:ring-1 focus:ring-[#2b5f8f]'

export default function RecruitmentFields({fields, errors = {}}: {
  fields: RecruitmentField[]
  errors?: Record<string, string>
}) {
  const prefix = useId()
  return <div className="space-y-5">
    {fields.map(field => {
      const id = `${prefix}-${field.id}`
      const error = errors[field.id]
      const label = <>{field.label || '未命名題目'}{field.required && <span className="ml-1 text-red-700">（必填）</span>}</>
      const name = field.type === 'file' ? `file_${field.id}` : `answer_${field.id}`
      const common = {id, name, required: field.required, 'aria-invalid': !!error, 'aria-describedby': error ? `${id}-error` : undefined}
      const formatInfo = field.formats?.map(format => recruitmentFileFormats[format])
      return <div key={field.id} className="min-w-0 space-y-2">
        {field.type === 'multiple' ? <fieldset aria-invalid={common['aria-invalid']} aria-describedby={common['aria-describedby']} className="space-y-2">
          <legend className="mb-2 text-sm font-semibold">{label}</legend>
          {field.options?.filter(Boolean).map((option, index) => <label key={index} className="flex min-h-8 items-center gap-2 text-sm">
            <input type="checkbox" name={name} value={option} />{option}
          </label>)}
        </fieldset> : <>
          <label htmlFor={id} className="block text-sm font-semibold">{label}</label>
          {field.type === 'long' && <textarea {...common} rows={4} maxLength={5000} className={inputClass} />}
          {field.type === 'short' && <input {...common} type="text" maxLength={200} className={inputClass} />}
          {field.type === 'single' && <select {...common} defaultValue="" className={inputClass}>
            <option value="">請選擇</option>
            {field.options?.filter(Boolean).map((option, index) => <option key={index} value={option}>{option}</option>)}
          </select>}
          {field.type === 'file' && <>
            <input {...common} type="file" accept={formatInfo?.map(format => format.accept).join(',')} className={inputClass}
              aria-describedby={[`${id}-hint`, common['aria-describedby']].filter(Boolean).join(' ')} />
            <p id={`${id}-hint`} className="text-xs opacity-80">{formatInfo?.map(format => format.label).join('／')} · 單檔上限 {field.max_mb} MB</p>
          </>}
        </>}
        {error && <p id={`${id}-error`} className="text-sm text-red-700">{error}</p>}
      </div>
    })}
  </div>
}

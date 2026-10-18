type Props = {metadata: Record<string, any>; options: {value:string;label:string}[]; onChange: (metadata: Record<string,any>)=>void}
export default function CourseAreaFields({metadata, options, onChange}: Props) {
  const selected: string[] = Array.isArray(metadata.resort_slugs) ? metadata.resort_slugs : []
  const all = [...options, ...selected.filter(slug=>!options.some(option=>option.value===slug)).map(slug=>({value:slug,label:`${slug}（雪場資料已移除）`}))]
  return <fieldset className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <legend className="px-2 text-sm font-semibold text-gray-900 dark:text-white">這個官網校區要顯示哪些雪場？</legend>
    <p className="mb-3 text-xs text-gray-600 dark:text-gray-300">只影響官網導覽，不會改動營運校區、訂單或員工權限。雪場可重複勾選到不同官網校區；依勾選順序排列。</p>
    {!all.length && <p className="text-sm text-gray-600 dark:text-gray-300">請先到「雪場列表」建立雪場。</p>}
    <div className="grid gap-2 sm:grid-cols-2">{all.map(option=><label key={option.value} className="flex min-h-11 items-center gap-3 rounded-lg bg-gray-50 px-3 text-sm text-gray-900 dark:bg-gray-800 dark:text-white"><input type="checkbox" checked={selected.includes(option.value)} onChange={event=>onChange({...metadata,resort_slugs:event.target.checked?[...selected,option.value]:selected.filter(slug=>slug!==option.value)})} />{option.label}{selected.includes(option.value) && <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">第{selected.indexOf(option.value)+1}個</span>}</label>)}</div>
  </fieldset>
}

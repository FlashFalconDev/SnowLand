const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), Module=require('node:module'), vm=require('node:vm')
const root=path.resolve(__dirname,'..'), localRequire=Module.createRequire(path.join(root,'package.json'))
const React=localRequire('react'),ts=localRequire('typescript'),{renderToStaticMarkup}=localRequire('react-dom/server')
let month='2026-10'
const context=vm.createContext({React,exports:{},require:()=>({...React,useState:()=>[month,value=>{month=value}],useMemo:fn=>fn()}),Date})
vm.runInContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/admin/components/InsuranceCalendar.tsx'),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,context)
const {insuranceMonthDays,insuranceDayRecords,default:Calendar}=context.exports
assert.equal(insuranceMonthDays('2024-02').filter(Boolean).length,29)
assert.equal(insuranceMonthDays('2026-02').filter(Boolean).length,28)
assert.equal(insuranceMonthDays('2026-11')[0],'2026-11-01')
const rows=[{id:1,course_dates:['2026-10-17','2026-10-17'],insurance_completed_at:null,insurance_processing_status:'pending'},
  {id:2,course_dates:['2026-10-17'],insurance_completed_at:'filled',insurance_processing_status:'insured'},
  {id:3,course_dates:[],insurance_completed_at:null,insurance_processing_status:'pending'}]
assert.equal(insuranceDayRecords(rows,'2026-10-17').length,2)
const selected=[]
const tree=Calendar({rows,selectedDate:'2026-10-17',onSelect:date=>selected.push(date)}),html=renderToStaticMarkup(tree)
assert.match(html,/2026-10-17，2 位學員，資料待補 1 位，資料已填 1 位，尚未投保或處理中 1 位，已投保 1 位/)
assert.match(html,/清除日期篩選/)
assert.match(html,/aria-pressed="true"/)
const buttons=[]
function walk(node){if(!node||typeof node!=='object')return;if(node.type==='button')buttons.push(node);React.Children.forEach(node.props?.children,walk)}
walk(tree)
buttons.find(button=>button.props['aria-label']?.startsWith('2026-10-17，')).props.onClick()
assert.equal(selected.pop(),'')
buttons.find(button=>button.props['aria-label']==='保險月曆下一個月').props.onClick()
assert.equal(month,'2026-11');assert.equal(selected.pop(),'')
console.log('PASS insurance calendar: leap dates, Sunday alignment, per-member/day deduplication, independent data/insurance counts, selected date and month navigation')

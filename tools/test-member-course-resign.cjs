const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json'))
const React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8')
const component=source.slice(source.indexOf('function PreCourseForm('),source.indexOf('function MissingStudents('))
const find=(node,p)=>{if(!node||typeof node!=='object')return null;if(p(node))return node;for(const child of React.Children.toArray(node.props?.children)){const result=find(child,p);if(result)return result}return null}
const form={id:42,age_range:'25-35y',insurance_data:{full_name:'QA',birth_date:'1995-01-01'},insurance_processing_status:'checking',snowboard_skills:[],ski_skills:[],waiver_signature:'OLD',waiver_completed:false,waiver_resign_required:true,waiver_course_revision:91,media_consent:'decline'}
const states=[],calls=[];let cursor=0,refreshed=0,reject=false
const context=vm.createContext({React,exports:{},ageOptions:['25-35y'],ageLabel:value=>value,birthDateStatus:()=>({age:31,error:''}),
 useSiteLocale:require('./helpers/site-locale-harness.cjs')(React).useSiteLocale,
 useState:initial=>{const index=cursor++;if(!(index in states))states[index]=typeof initial==='function'?initial():initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value]},
 requestJson:async(url,options)=>{calls.push(JSON.parse(options.body));if(reject)throw Error('課程已變更，請重新載入課前資料，再閱讀及簽署聲明書');return{message:'已儲存'}},
})
vm.runInContext(ts.transpileModule(component,{fileName:'resign.jsx',compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,context)
const render=()=>{cursor=0;return context.PreCourseForm({form,waiverDocument:{title:'QA',version:'same-version',body:'QA無法律效力',reference_date:'2026-10-19'},skillOptions:{},onSaved:async()=>{refreshed++}})}
const button=name=>find(render(),node=>node.type==='button'&&node.props.children===name)
async function main(){
 assert.match(renderToStaticMarkup(render()),/原簽署已留底/)
 assert.match(renderToStaticMarkup(render()),/投保作業：行政核對中/)
 assert.match(renderToStaticMarkup(render()),/填妥資料不代表已完成投保/)
 assert.equal(states[1].waiver_signature,'','A changed course must not prefill the old signature')
 assert.equal(states[1].waiver_agreed,false)
 button('填寫／修改資料').props.onClick()
 states[1]={...states[1],waiver_agreed:true}
 assert.equal(button('儲存課前資料').props.disabled,true,'Must enter a new signature')
 states[1]={...states[1],waiver_signature:'QA NEW'}
 assert.equal(button('儲存課前資料').props.disabled,false)
 reject=true;await button('儲存課前資料').props.onClick()
 assert.equal(calls[0].waiver_course_revision,91)
 assert.equal(calls[0].waiver_signature,'QA NEW')
 assert.equal(states[1].waiver_signature,'QA NEW','A rejected stale signature keeps the draft')
 assert.equal(refreshed,0)
 const reload=button('重新載入（放棄未儲存內容）');assert.ok(reload.props.className.includes('min-h-11'))
 reload.props.onClick();assert.equal(states[0],false);assert.equal(refreshed,1)
 console.log('PASS actual member course-resign controls: old signature cleared, explicit new signature, course revision proof, stale rejection retains draft and named reload')
}
main().catch(error=>{console.error(error);process.exitCode=1})

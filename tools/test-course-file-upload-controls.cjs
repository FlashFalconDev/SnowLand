const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module'), vm = require('node:vm')
const root = path.resolve(__dirname, '../snowland-frontend')
const req = Module.createRequire(path.join(root, 'package.json'))
const React = req('react'), ts = req('typescript'), {renderToStaticMarkup} = req('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/admin/pages/OperationsHubPage.tsx'), 'utf8')
const actual = source.slice(source.indexOf('function CourseFileUploader('), source.indexOf('function BookingLinksPanel('))
const compile = ts.transpileModule(actual, {compilerOptions:{jsx:ts.JsxEmit.React, module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2020}}).outputText
function walk(node, predicate) {
  if (!node || typeof node !== 'object') return []
  return [...(predicate(node) ? [node] : []), ...React.Children.toArray(node.props?.children).flatMap(child => walk(child, predicate))]
}
function harness({file=null, limits={formats:['PNG','MP4'],photo_limit_bytes:20,video_limit_bytes:100},pending=false,error=false,percent=0,coachView=false}={}) {
  const state=[file,percent,''], busy=[], calls=[], invalidations=[]
  const input={current:{value:file?.name || ''}}
  let cursor=0, options, retries=0
  const ctx=vm.createContext({React,Math,Boolean,
    useRef:()=>input,
    useState:()=>{const i=cursor++;return[state[i],value=>state[i]=value]},
    useQueryClient:()=>({invalidateQueries:async args=>invalidations.push(args)}),
    useQuery:()=>({data:limits,isError:error,refetch(){retries++}}),
    useMutation:value=>{options=value;return{isPending:pending,isError:error,reset(){},mutate(){calls.push('mutate')}}},
    fetchCourseUploadLimits(){}, uploadCourseFile:async(...args)=>calls.push(args),
  })
  vm.runInContext(compile,ctx)
  const render=()=>{cursor=0;return ctx.CourseFileUploader({evaluationId:23,coachView,onBusyChange:value=>busy.push(value)})}
  return {render,state,busy,calls,invalidations,input,options:()=>options,retries:()=>retries}
}
const button=tree=>walk(tree,node=>node.type==='button').at(-1)
async function main() {
  for(const config of [{},{file:{name:'qa.png',type:'image/png',size:21}},{file:{name:'qa.mp4',type:'video/mp4',size:101}},{file:{name:'qa.png',type:'image/png',size:1},limits:null},{file:{name:'qa.png',type:'image/png',size:1},pending:true}]) {
    assert.equal(button(harness(config).render()).props.disabled,true)
  }
  const photo={name:'qa.png',type:'image/png',size:20}
  const valid=harness({file:photo,coachView:true}); const tree=valid.render()
  assert.equal(button(tree).props.disabled,false)
  assert.equal(walk(tree,node=>node.type==='input')[0].props.accept.includes('video/mp4'),true)
  valid.options().onMutate();assert.equal(valid.busy[0],true);assert.equal(valid.state[1],0)
  await valid.options().mutationFn();assert.equal(valid.calls[0][0],23);assert.equal(valid.calls[0][1],photo);assert.equal(valid.calls[0][2],true)
  await valid.options().onSuccess();valid.options().onSettled()
  assert.equal(valid.state[0],null);assert.equal(valid.input.current.value,'');assert.match(valid.state[2],/附件已上傳/)
  assert.deepEqual(Array.from(valid.invalidations[0].queryKey),['coach','evaluations']);assert.equal(valid.busy.at(-1),false)
  const failed=harness({file:photo,error:true});failed.render()
  failed.options().onError({response:{data:{msg:'QA 儲存失敗'}}});failed.options().onSettled()
  assert.equal(failed.state[0],photo);assert.equal(failed.state[2],'QA 儲存失敗');assert.equal(failed.busy.at(-1),false)
  const retryTree=failed.render();assert.equal(button(retryTree).props.children,'重試上傳');assert.equal(button(retryTree).props.disabled,false)
  const pendingHtml=renderToStaticMarkup(harness({file:photo,pending:true,percent:100}).render())
  assert.match(pendingHtml,/傳送完成，正在檢查與儲存/)
  const loadFailure=harness({error:true,limits:null});walk(loadFailure.render(),node=>node.type==='button')[0].props.onClick();assert.equal(loadFailure.retries(),1)
  console.log('PASS actual course file uploader controls: no-file/limits/size/busy guards, exact boundary, private role endpoint, progress, success cleanup/cache, failure retains file/retry, settings retry')
}
main().catch(error=>{console.error(error);process.exitCode=1})

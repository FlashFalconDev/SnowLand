const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'../snowland-frontend'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript')
const source=fs.readFileSync(path.join(root,'src/pages/BookingFlowPage.tsx'),'utf8')
const fragment=source.match(/<select\s+aria-label=\{`\$\{level\.name\}學員人數`\}[\s\S]*?<\/select>/)?.[0]
assert.ok(fragment,'The actual booking grade selector must have an accessible name')
const changes=[],ctx=vm.createContext({React,exports:{},count:2,maxSelectable:4,level:{id:'no_exp',name:'等級 0'},actions:{setAbilityLevelCount:(...args)=>changes.push(args)}})
vm.runInContext(ts.transpileModule(`exports.control=(${fragment})`,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,ctx)
const node=ctx.exports.control
assert.equal(node.props['aria-label'],'等級 0學員人數')
assert.match(node.props.className,/min-h-11/)
assert.equal(node.props.value,2)
assert.equal(React.Children.toArray(node.props.children).length,5)
node.props.onChange({target:{value:'3'}})
assert.deepEqual(changes,[['no_exp',3]])
console.log('PASS actual JSX: named ability control, 44px minimum, retained count, bounded options and numeric update callback')
const dateStart=source.indexOf('const toDateKey = '),dateEnd=source.indexOf('\n}',dateStart)+2
const dateContext=vm.createContext({exports:{},Date:class {
  getFullYear(){return 2026} getMonth(){return 9} getDate(){return 19}
  toISOString(){return '2026-10-18T17:00:00.000Z'}
}})
vm.runInContext(ts.transpileModule(source.slice(dateStart,dateEnd),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText,dateContext)
for(const match of source.matchAll(/const today = ([^\r\n]+)/g)){
  if(!/^(toDateKey|new Date)/.test(match[1]))continue
  vm.runInContext(`exports.today = ${match[1]}`,dateContext)
  assert.equal(dateContext.exports.today,'2026-10-19',`Booking date validation and hints must agree on the visitor's local day: ${match[1]}`)
}
console.log('PASS booking validation and both calendar notices agree at local 01:00, not the prior UTC date')
const calendar=fs.readFileSync(path.join(root,'src/admin/pages/my/MyCalendarPage.tsx'),'utf8')
for(const label of ['月曆上一個月','月曆下一個月']){
 const button=calendar.split(/\r?\n/).find(line=>line.includes(`aria-label="${label}"`))
 assert.ok(button&&button.includes('min-h-11')&&button.includes('min-w-11'),'Coach calendar navigation needs named 44px controls')
}
const coachCourses=fs.readFileSync(path.join(root,'src/admin/pages/my/MyCoursesPage.tsx'),'utf8')
assert.match(coachCourses,/type="month"\s+aria-label="統計月份"[\s\S]*?className="min-h-11/)
const orders=fs.readFileSync(path.join(root,'src/admin/pages/OrdersPage.tsx'),'utf8')
assert.equal(orders.split('aria-label={`查看訂單 ${order.sn}`}').length-1,2,'Desktop and mobile order controls must identify the exact order')
for(const handler of ['setConfirmCompletionId(null)','completeCourse.mutate(r.id)','setConfirmCompletionId(r.id)'])assert.ok(orders.split(/\r?\n/).find(line=>line.includes(handler)&&line.includes('<button')).includes('min-h-11'),'Completion/return controls need44px touch targets')

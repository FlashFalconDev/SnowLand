const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const values=new Map()
global.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}
const window={location:{pathname:'/school-a/booking'}}
const tenant=require('./helpers/tenant-harness.cjs')(window,global.localStorage)
assert.equal(tenant.currentClientCode(),'school-a')
values.set('client_code','school-b')
assert.equal(tenant.currentClientCode(),'school-a','URL must win over stale browser school')
for(const path of ['/','/auth/callback','/api/admin/test','/booking/test']) {
  assert.equal(tenant.clientCodeFromPath(path),null)
}
const filename=path.resolve(__dirname,'../src/store/bookingStore.ts')
const loaded=new Module(filename,module);loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename))
const originalRequire=loaded.require.bind(loaded)
loaded.require=name=>name==='@/utils/tenant'?tenant:originalRequire(name)
loaded._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename)
const {getSchoolBookingStore,useBookingStore}=loaded.exports
const a=getSchoolBookingStore('school-a'),b=getSchoolBookingStore('school-b')
a.setState({cart:[{id:'A'}]});b.setState({cart:[{id:'B'}]})
assert.equal(useBookingStore.getState().cart[0].id,'A')
window.location.pathname='/school-b/booking'
assert.equal(useBookingStore.getState().cart[0].id,'B')
// An action already captured in A must keep writing to A after navigation to B.
a.getState().clearCart()
assert.equal(a.getState().cart.length,0)
assert.equal(b.getState().cart[0].id,'B')
assert.equal(JSON.parse(values.get('booking-storage:school-b')).state.cart[0].id,'B')
assert.equal(values.has('booking-storage'),false,'Never read or overwrite ambiguous legacy cart')
assert.notEqual(tenant.campusScopeKey('school-a'),tenant.campusScopeKey('school-b'))
window.location.pathname='/'
assert.throws(()=>tenant.currentClientCode(),/學校/)
assert.deepEqual(useBookingStore.getState().cart,[],'Public landing must not inherit any school cart')
console.log('PASS URL selection, callback guard, two-school carts, delayed actions and scoped persistence')

assert.equal(tenant.tenantReturnPath('/school-a/membership?tab=orders','school-a'),'/school-a/membership?tab=orders')
for(const next of ['https://evil.test/','//evil.test/','/school-b/','/school-a/../school-b/','/school-a/%2e%2e/school-b/',null]) {
  assert.equal(tenant.tenantReturnPath(next,'school-a'),'/school-a','Login return stays in the original school')
}

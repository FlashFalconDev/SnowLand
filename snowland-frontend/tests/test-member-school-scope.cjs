const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm')
const window={location:{pathname:'/school-a/membership'}},storage={getItem:()=>null}
const tenant=require('./helpers/tenant-harness.cjs')(window,storage)
const source=fs.readFileSync(path.join(__dirname,'../src/pages/site/MembershipPage.jsx'),'utf8')
const start=source.indexOf('async function requestJson('),end=source.indexOf('\nfunction EmptyState(',start),calls=[]
const ctx=vm.createContext({Headers,document:{cookie:'csrftoken=local-qa'},schoolBookingApiPath:tenant.schoolBookingApiPath,
 fetch:async(url,options)=>{calls.push({url,options});return{ok:true,status:200,json:async()=>({ok:true})}}})
vm.runInContext(source.slice(start,end),ctx)
;(async()=>{
 for(const school of ['school-a','school-b','school-a']) {
  window.location.pathname='/'+school+'/membership'
  for(const endpoint of ['/member-auth/','/member-center/','/member-notifications/?page=2','/member-cancellations/8/','/participant-invitations/qa/','/member-amendments/8/']) {
   await ctx.requestJson(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
   assert.equal(calls.at(-1).url,'/booking/'+school+'/api'+endpoint)
   assert.equal(calls.at(-1).options.credentials,'include')
   assert.equal(calls.at(-1).options.headers.get('X-CSRFToken'),'local-qa')
  }
 }
 await ctx.requestJson('/control/api/logout/',{method:'POST'})
 assert.equal(calls.at(-1).url,'/control/api/logout/')
 window.location.pathname='/'
 await assert.rejects(()=>ctx.requestJson('/member-center/'),/學校/)
 assert.ok(!source.includes('/booking/snowland/'),'member screens must not pin another school')
 const balance=fs.readFileSync(path.join(__dirname,'../src/components/OrderAmendmentBalance.jsx'),'utf8')
 assert.ok(!balance.includes('/booking/snowland/'),'amendment screen uses the same scoped request helper')
 console.log('PASS real member request helper: school A/B/A endpoints, credentials/CSRF, logout and unselected-school rejection')
})().catch(e=>{console.error(e);process.exitCode=1})

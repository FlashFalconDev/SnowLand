const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),vm=require('node:vm')
const root=path.resolve(__dirname,'..'),req=Module.createRequire(path.join(root,'package.json')),React=req('react'),ts=req('typescript'),{renderToStaticMarkup}=req('react-dom/server')
const source=fs.readFileSync(path.join(root,'src/pages/site/MembershipPage.jsx'),'utf8')
const between=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)))
const code=between('function ParticipantRoster(','function ParticipantInvitation(')+between('function MemberSection(','function MemberContent(')+between('function SatisfactionForm(','function Overview(')+between('function ParticipantCourses(','function MemberNotifications(')
const progressContext={exports:{}}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'src/utils/learningProgress.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,progressContext)
assert.equal(progressContext.exports.formatLearningProgressEntry('before','level2'),'課前程度：等級 2','Existing admin formatting is unchanged')
for(const language of ['en','ja']){
  const locale=require('./helpers/site-locale-harness.cjs')(React,language)
  for(const message of [
    '邀請已撤銷，舊連結無法使用','邀請連結已產生，請只傳給這位學員或他的家長',
    '找不到邀請連結，可能已撤銷或重新產生','邀請連結已過期，請訂購人重新產生連結',
    '此學員已綁定帳號，不能重新邀請或撤銷綁定','綁定完成，您可以填寫自己的課前資料',
  ]) assert.notEqual(locale.translateSiteText(language,message),message,`${language}: ${message}`)
  let cursor=0
  const states=[null,{7:{url:'https://example.test/qa-invite',expires:'2026-10-20T00:00:00Z'}},'', '']
  const context={React,window:{location:{origin:'https://example.test'}},navigator:{},SiteBasePathContext:{},useContext:()=>'/snowland',useState:()=>{const index=cursor++;return[states[index],()=>{}]},useSiteLocale:require('./helpers/site-locale-harness.cjs')(React,language).useSiteLocale,Gift:()=>null,Star:()=>null,formatDate:value=>value,formatLearningProgressEntry:progressContext.exports.formatLearningProgressEntry,ClassGroupQRImage:()=>null,SiteLink:({to,children,...props})=>React.createElement('a',{href:to,...props},children)}
  vm.runInNewContext(ts.transpileModule(code,{fileName:'member.jsx',compilerOptions:{jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2020}}).outputText,context)
  const offers=renderToStaticMarkup(context.MemberSection({section:'offers',data:{level:'silver',alumni_verified:true,points:123,previous_points:45,referral_code:'QA-<private>-123'}}))
  for(const text of ['銀級','目前點數','歷史補登'])assert.ok(!offers.includes(text),language+' untranslated '+text)
  assert.ok(offers.includes('123')&&offers.includes('45'))
  assert.ok(offers.includes('QA-&lt;private&gt;-123'),'Referral code preserved and escaped')
  assert.ok(offers.includes(language==='en'?'Silver':'シルバー'))
  const roster=renderToStaticMarkup(context.ParticipantRoster({order:{order_number:'QA-123',payment_status:'paid'},reservation:{resort:'QA雪場名稱',participants:[{id:7,student_number:2,binding_status:'pending',can_invite:true}]},onSaved(){}}))
  assert.ok(roster.includes('QA雪場名稱'),'CMS name remains unchanged')
  for(const text of ['的邀請網址','有效至','請勿公開分享'])assert.ok(!roster.includes(text))
  assert.ok(roster.includes('https://example.test/qa-invite')&&roster.includes(new Date(states[1][7].expires).toLocaleDateString(language)))
  console.log('PASS actual member offers and invitation roster locale',language)
  context.useState=React.useState
  const record={id:1,date:'2026-10-20',order_number:'QA-123',resort:'QA雪場名稱',course_name:'QA課程名稱',member_name:'私人姓名QA',coach:'私人教練QA',coach_notes:'教練私人評語，不翻譯',trail_names:['原始雪道QA'],media:[],learning_progress:{before:'level2',custom_key:'原始自訂進度'},self_assessment:{satisfaction_rating:4}}
  const journey=renderToStaticMarkup(React.createElement(context.Journey,{records:[record]}))
  for(const value of ['私人姓名QA','私人教練QA','教練私人評語，不翻譯','原始雪道QA','原始自訂進度'])assert.ok(journey.includes(value),'Personal/CMS content must remain unchanged')
  for(const value of ['學員：','教練：','本次雪道：','課前程度','等級 2'])assert.ok(!journey.includes(value),'Owned UI must translate: '+value)
  assert.ok(journey.includes(language==='en'?'Ability before lesson':'受講前レベル'))
  assert.ok(journey.includes(language==='en'?'Level 2':'レベル2'))
  assert.ok(journey.includes(language==='en'?'aria-label="Rating: 1"':'aria-label="評価：1点"'))
  assert.ok(journey.includes('min-h-11 min-w-11'),'Rating controls retain 44px touch targets')
  assert.equal((journey.match(/aria-pressed="true"/g)||[]).length,1)
  assert.equal(progressContext.exports.formatLearningProgressEntry('private_key','課前程度',context.useSiteLocale().t),'private_key：課前程度','Unknown custom data is not translated even when text resembles a UI label')
  const courses=renderToStaticMarkup(React.createElement(context.ParticipantCourses,{courses:[{id:1,status:'confirmed',payment_status:'paid',resort:'QA雪場名稱',course_name:'QA課程名稱',student_names:['私人姓名QA'],coach:'私人教練QA',bookings:[]}]}))
  assert.ok(courses.includes('私人姓名QA')&&courses.includes('私人教練QA'))
  assert.ok(!courses.includes('學員：')&&!courses.includes('教練：'))
  console.log('PASS actual learning records and participant course locale',language)
}

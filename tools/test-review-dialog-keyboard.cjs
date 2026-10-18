const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const source = fs.readFileSync(path.resolve(__dirname, '../snowland-frontend/src/pages/site/CoachPage.jsx'), 'utf8').replace(/\r\n/g, '\n')
const closeButtons = [...source.matchAll(/<button\s+type="button"\s+className="([^"]+)"\s+onClick=\{\(\) => setSelectedCashReview(?:Photo)?\(null\)\}/g)]
assert.equal(closeButtons.length,2,'review and photo overlays both need close controls')
for(const [,classes] of closeButtons)assert.ok(classes.includes('min-h-11') && classes.includes('min-w-11'),'mobile overlay close controls must be at least44px')
const body = source.match(/useEffect\(\(\) => \{\n(    const dialog = selectedCashReviewPhoto \? reviewPhotoDialogRef.current[\s\S]*?)\n  \}, \[selectedCashReview, selectedCashReviewPhoto\]\);/)
assert.ok(body, 'actual review dialog keyboard effect must exist')
const run = new Function('document', 'selectedCashReviewPhoto', 'reviewPhotoDialogRef', 'reviewDialogRef', 'setSelectedCashReviewPhoto', 'setSelectedCashReview', body[1])
for (const photo of [false, true]) {
  const doc = {body:{style:{overflow:'auto'}}, addEventListener(_, fn){this.handler=fn}, removeEventListener(_, fn){assert.equal(fn,this.handler);this.handler=null}}
  const trigger = {isConnected:true, focus(){doc.activeElement=this}}
  const first = {focus(){doc.activeElement=this}}, last = {focus(){doc.activeElement=this}}
  const dialog = {querySelectorAll:()=>[first,last], contains:node=>node===first||node===last}
  let closedReview=0, closedPhoto=0
  doc.activeElement=trigger
  const cleanup=run(doc,photo,{current:dialog},{current:dialog},()=>closedPhoto++,()=>closedReview++)
  assert.equal(doc.activeElement,first); assert.equal(doc.body.style.overflow,'hidden')
  let prevented=0
  const key=(key,shiftKey=false)=>doc.handler({key,shiftKey,preventDefault(){prevented++}})
  key('Tab',true); assert.equal(doc.activeElement,last)
  key('Tab'); assert.equal(doc.activeElement,first)
  doc.activeElement=trigger; key('Tab'); assert.equal(doc.activeElement,first)
  key('Escape'); assert.equal(closedPhoto,photo?1:0); assert.equal(closedReview,photo?0:1)
  assert.equal(prevented,4)
  cleanup(); assert.equal(doc.activeElement,trigger); assert.equal(doc.body.style.overflow,'auto'); assert.equal(doc.handler,null)
}
assert.equal(run({},false,{current:null},{current:null},()=>{},()=>{}),undefined)
console.log('PASS actual review and photo dialog effect: initial focus, forward/reverse Tab wrapping, escaped focus, Escape top-layer close, scroll and focus restoration, cleanup')

const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { join } = require('node:path')
const { test } = require('node:test')

const readSource = file => readFileSync(join(__dirname, '../src', file), 'utf8')

test('the shared coach photo style covers its frame and aligns to the top', () => {
  const declarations = readSource('index.css').match(/\.coach-photo\s*\{([^}]+)\}/)?.[1] ?? ''
  assert.match(declarations, /object-fit:\s*cover\s*;/)
  assert.match(declarations, /object-position:\s*center top\s*;/)
})

const coachPhotos = [
  ['pages/BookingFlowPage.tsx', 'coach.image'],
  ['admin/components/ImageUploadField.tsx', 'current'],
  ['admin/pages/cms/CoachEditorPage.tsx', 'cleanImageValue(coach.img)'],
  ['admin/pages/CoachesPage.tsx', 'coach.img'],
  ['admin/pages/CoachLeavesPage.tsx', 'leave.coach_img'],
]

for (const [file, source] of coachPhotos) {
  test(`${file} uses the shared coach photo style`, () => {
    const images = readSource(file).match(/<img\b[\s\S]*?\s\/>/g) ?? []
    const image = images.find(tag => tag.includes(`src={${source}}`))
    assert.ok(image, `Missing coach photo with src={${source}}`)

    const classes = image.match(/className="([^"]+)"/)?.[1].split(/\s+/) ?? []
    assert.ok(classes.includes('coach-photo'))
    assert.ok(classes.every(className => !className.startsWith('object-')))
    if (file === 'pages/BookingFlowPage.tsx') assert.ok(classes.includes('aspect-[5/4]'))
  })
}

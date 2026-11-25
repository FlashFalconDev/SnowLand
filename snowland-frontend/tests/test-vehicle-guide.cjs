const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { Outlet, Route, Routes, StaticRouter } = require('react-router-dom')
const ts = require('typescript')

const sourceRoot = path.resolve(__dirname, '../src/admin')
const cache = new Map()
const SiteBasePathContext = React.createContext('/demo')
const emptyModule = { default: () => null }
let signedInUser

function load(file) {
  if (cache.has(file)) return cache.get(file)
  const source = fs.readFileSync(path.join(sourceRoot, file), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  } }).outputText
  const module = { exports: {} }
  new Function('require', 'module', 'exports', code)(specifier => {
    if (specifier === 'react' && file === 'components/RoleGuard.tsx') {
      // Feed resolved access into the guard so it can render without async effects.
      return { ...React, useState: () => [signedInUser, () => {}] }
    }
    if (specifier === '@/components/site/SiteLink') return { SiteBasePathContext }
    if (!specifier.startsWith('.')) return require(specifier)
    if (specifier === './layout/AdminLayout') return { default: Outlet }
    const localFile = path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier))
    const extension = ['.tsx', '.ts'].find(ext => fs.existsSync(path.join(sourceRoot, localFile + ext)))
    const tested = ['components/RoleGuard', 'consoleNavigation', 'permissions', 'pages/VehiclePage', 'pages/help/VehicleGuidePage']
    return tested.includes(localFile) ? load(localFile + extension) : emptyModule
  }, module, module.exports)
  cache.set(file, module.exports)
  return module.exports
}

const AdminRoutes = load('AdminRoutes.tsx').default
function render(pathname, user) {
  signedInUser = user
  const location = `/demo/console/${pathname}`
  return renderToStaticMarkup(React.createElement(StaticRouter, { location },
    React.createElement(Routes, null,
      React.createElement(Route, { path: '/:clientCode/console/*', element: React.createElement(AdminRoutes) }),
    ),
  ))
}

const guidePath = 'help/vehicles'
const manager = { is_manager: true, role: 'campus_manager', permissions: ['vehicle_review'] }
const finance = { is_manager: true, role: 'assistant', permissions: ['vehicle_finance'] }
const coach = { is_coach: true, permissions: [] }
const denied = { is_manager: true, role: 'assistant', permissions: [] }

for (const [vehiclePath, anchor, user] of [
  ['vehicles/review', 'review', manager],
  ['vehicles/finance', 'finance', finance],
  ['my/vehicles', 'coach', coach],
]) {
  const operation = render(vehiclePath, user)
  assert.match(operation, new RegExp(`href="/demo/console/${guidePath}#${anchor}"`))
  assert.match(operation, /> 使用說明<\/a>/)
  const guide = render(`${guidePath}#${anchor}`, user)
  assert.match(guide, /<h1[^>]*>車輛用車說明<\/h1>/)
  assert.match(guide, new RegExp(`id="${anchor}"`))
  for (const chapter of ['整體流程', '開始前確認', '圖文操作', '完成結果', '常見問題', '來源與更新']) {
    assert.match(guide, new RegExp(`<h2[^>]*>${chapter}</h2>`))
  }
  assert.match(guide, /<h3[^>]*>出車、還車與支出<\/h3>/)
  assert.match(guide, /<h3[^>]*>費用核准、薪扣與人工收款<\/h3>/)
}

const images = [...render(guidePath, finance).matchAll(/<img src="(\/vehicle-guide\/[^"]+\.webp)"/g)]
assert.equal(images.length, 9)
for (const [, url] of images) {
  assert.ok(fs.existsSync(path.resolve(__dirname, '../public', '.' + url)), `Missing guide screenshot: ${url}`)
}

for (const user of [denied, { ...denied, permissions: ['vehicle_review'] }, { is_coach: false }]) {
  const result = render(guidePath, user)
  assert.match(result, /沒有功能權限/)
  assert.doesNotMatch(result, /車輛用車說明/)
}

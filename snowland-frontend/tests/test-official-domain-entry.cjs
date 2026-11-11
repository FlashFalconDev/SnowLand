const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/pages/ClientSelectionPage.tsx'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.React },
}).outputText

function render(hostname) {
  const location = { pathname: '/', search: '?utm_source=official', hash: '#courses' }
  const context = {
    exports: {}, React, window: { location: { ...location, hostname } },
    require(name) {
      if (name === 'react') return { useState: initial => [initial, () => {}] }
      if (name === 'react-router-dom') return {
        Navigate: 'redirect', useLocation: () => location, useNavigate: () => () => {},
      }
      if (name === '@/utils/tenant') return {}
      throw new Error(name)
    },
  }
  vm.runInNewContext(compiled, context)
  return context.exports.default()
}

for (const hostname of ['snowland.tw', 'www.snowland.tw']) {
  const view = render(hostname)
  assert.equal(view.type, 'redirect', `${hostname} must open the SnowLand website`)
  assert.equal(view.props.to.pathname, '/snowland/')
  assert.equal(view.props.to.search, '?utm_source=official')
  assert.equal(view.props.to.hash, '#courses')
  assert.equal(view.props.replace, true)
}

for (const hostname of ['localhost', '127.0.0.1', 'other-school.example', 'snowland.tw.example']) {
  assert.equal(render(hostname).type, 'main', `${hostname} keeps school selection`)
}
console.log('PASS official domains open SnowLand, preserve the link, and keep other domain entry independent')

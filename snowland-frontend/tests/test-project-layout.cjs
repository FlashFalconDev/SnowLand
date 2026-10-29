const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const frontend = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(frontend, 'vite.config.ts'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true},
}).outputText

function configure(files, environment = {}, mode = 'development') {
  let loadedDirectory
  const scope = {
    exports: {}, __dirname: frontend, process: {env: environment},
    require(name) {
      if (name === 'vite') return {
        defineConfig: value => value,
        loadEnv: (_mode, directory, prefix) => {
          assert.equal(prefix, 'VITE_')
          loadedDirectory = directory
          return {VITE_API_TARGET: 'http://127.0.0.1:8999'}
        },
      }
      if (name === '@vitejs/plugin-react') return () => ({name: 'react-test'})
      if (name === 'node:fs') return {existsSync: file => files.includes(path.basename(file))}
      return require(name)
    },
  }
  vm.runInNewContext(compiled, scope)
  return {config: scope.exports.default({mode}), directory: () => loadedDirectory}
}
for (const file of ['.env', '.env.local', '.env.production', '.env.production.local']) {
  const result = configure([file], {}, 'production')
  assert.equal(result.directory(), frontend, 'Frontend settings must take precedence')
  assert.equal(result.config.envDir, frontend)
}
const legacy = configure([])
assert.equal(legacy.directory(), path.resolve(frontend, '..'), 'Existing root settings must keep working on upgrade')
assert.equal(legacy.config.server.port, 3000)
assert.equal(legacy.config.server.strictPort, true, 'Occupied port must fail instead of silently choosing another')
for (const proxy of Object.values(legacy.config.server.proxy)) {
  assert.equal(proxy.target, 'http://127.0.0.1:8999')
}
const override = configure(['.env.local'], {VITE_API_TARGET: 'http://127.0.0.1:8998'})
for (const proxy of Object.values(override.config.server.proxy)) {
  assert.equal(proxy.target, 'http://127.0.0.1:8998', 'Explicit process setting retains precedence')
}
console.log('PASS frontend settings ownership, legacy upgrade, proxy and fixed port')

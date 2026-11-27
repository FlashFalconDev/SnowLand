const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {join} = require('node:path')
const vm = require('node:vm')
const React = require('react')
const ts = require('typescript')
const {renderToStaticMarkup} = require('react-dom/server')

const source = readFileSync(join(__dirname, '../src/admin/components/LearnerCourseTools.tsx'), 'utf8')
const {outputText} = ts.transpileModule(source, {
  compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
})
const photoLimit = 20 * 1048576
const videoLimit = 100 * 1048576

function walk(node, matches) {
  if (!node || typeof node !== 'object') return []
  return [...(matches(node) ? [node] : []), ...React.Children.toArray(node.props?.children).flatMap(child => walk(child, matches))]
}

function harness() {
  let album = {
    assets: [
      {id: 51, can_delete: true, type: 'photo', url: '/private/photo', tagged_member_ids: [9]},
      {id: 52, can_delete: false, type: 'video', url: '/private/video', tagged_member_ids: []},
    ],
    members: [{id: 9, name: '測試學員'}],
    photo_limit_bytes: photoLimit,
    video_limit_bytes: videoLimit,
  }
  const state = []
  const refs = []
  const mutations = []
  const posted = []
  const removed = []
  const fetched = []
  const confirmed = []
  let stateIndex, refIndex, mutationIndex, pendingRequest, queryOptions
  let failUpload = true
  let failDelete = true
  let acceptDelete = false
  let refetches = 0
  class UploadForm {
    append(name, value) {
      assert.equal(name, 'file')
      this.file = value
    }
  }
  const api = {
    get: async path => { fetched.push(path); return {data: album} },
    post: async (path, body, config) => {
      posted.push([path, body.file.name])
      config.onUploadProgress({loaded: 1, total: 2})
      if (posted.length === 1) await new Promise(resolve => { pendingRequest = resolve })
      config.onUploadProgress({loaded: 2, total: 2})
      if (body.file.name === 'retry.jpg' && failUpload) {
        failUpload = false
        throw {response: {data: {msg: '「retry.jpg」：儲存暫時失敗'}}}
      }
    },
    delete: async (path, config) => {
      removed.push([path, config.params.asset_id])
      if (failDelete) {
        failDelete = false
        throw {response: {data: {msg: '暫時無法刪除相簿檔案，請稍後重試'}}}
      }
    },
  }
  const hooks = {
    useQuery: options => {
      queryOptions = options
      return {data: album, refetch: async () => { refetches++ }}
    },
    useQueryClient: () => ({
      cancelQueries: async () => {},
      setQueryData: (_key, update) => { album = update(album) },
    }),
    useMutation: options => {
      const index = mutationIndex++
      const mutation = mutations[index] ||= {}
      return {...mutation, mutate(variables) {
        mutation.isPending = true
        mutation.isError = mutation.isSuccess = false
        mutation.variables = variables
        mutation.result = (async () => {
          try {
            const data = await options.mutationFn(variables)
            await options.onSuccess?.(data, variables)
            mutation.isSuccess = true
          } catch (error) {
            mutation.isError = true
            mutation.error = error
          } finally {
            mutation.isPending = false
          }
        })()
      }}
    },
  }
  const modules = {
    react: {
      useState(initial) {
        const index = stateIndex++
        if (index >= state.length) state.push(initial)
        return [state[index], update => { state[index] = typeof update === 'function' ? update(state[index]) : update }]
      },
      useRef: () => refs[refIndex++] ||= {},
      useEffect() {},
    },
    'react/jsx-runtime': require('react/jsx-runtime'),
    '@tanstack/react-query': hooks,
    '@/utils/tenant': {currentClientCode: () => 'example-school'},
    '../api/axios': {default: api},
  }
  const exports = {}
  vm.runInNewContext(outputText, {
    require: name => modules[name], exports, FormData: UploadForm, AbortController,
    window: {confirm: message => { confirmed.push(message); return acceptDelete }},
  })
  return {
    render(coachView = true) {
      stateIndex = refIndex = mutationIndex = 0
      return exports.CoachCourseAlbum({bookingId: 23, coachView})
    },
    finishUpload: () => pendingRequest(),
    acceptDelete: () => { acceptDelete = true },
    result: index => mutations[index].result,
    fetch: () => queryOptions.queryFn(),
    refetches: () => refetches,
    posted, removed, fetched, confirmed,
  }
}

const input = tree => walk(tree, node => node.type === 'input')[0]
const button = (tree, text) => walk(tree, node => node.type === 'button' && node.props.children === text)[0]
const file = (name, type, size = 1) => ({name, type, size})

async function testUploads() {
  const demo = harness()
  const setup = demo.render()
  const picker = input(setup)
  assert.equal(picker.props.multiple, true)
  assert.equal(button(setup, '上傳到共用相簿').props.disabled, true)
  const first = file('first.png', '', photoLimit)
  const retry = file('retry.jpg', 'image/jpeg')
  const last = file('last.MOV', 'video/quicktime', videoLimit)
  const selection = {value: 'selected', files: [
    first, retry, last, file('iphone.HEIF', ''), file('mislabeled.jpg', 'image/heic'),
    file('oversized.webp', 'image/webp', photoLimit + 1), file('oversized.mp4', 'video/mp4', videoLimit + 1),
    file('unsupported.gif', 'image/gif'),
  ]}
  picker.props.onChange({currentTarget: selection})
  assert.equal(selection.value, '')
  const selected = demo.render()
  const html = renderToStaticMarkup(selected)
  assert.match(html, /iphone\.HEIF.*HEIC 格式暫不支援/)
  assert.match(html, /mislabeled\.jpg.*最相容/)
  assert.match(html, /oversized\.webp.*照片不可超過 20 MB/)
  assert.match(html, /oversized\.mp4.*影片不可超過 100 MB/)
  assert.match(html, /unsupported\.gif.*格式不支援/)
  button(selected, '上傳到共用相簿').props.onClick()
  assert.deepEqual(demo.posted, [['/coach/course-albums/23/', 'first.png']])
  const inProgress = demo.render()
  assert.equal(input(inProgress).props.disabled, true)
  assert.equal(walk(inProgress, node => node.type === 'progress')[0].props.value, 50)

  demo.finishUpload()
  await demo.result(0)
  assert.deepEqual(demo.posted.map(([, name]) => name), ['first.png', 'retry.jpg', 'last.MOV'])
  const finished = demo.render()
  const resultHtml = renderToStaticMarkup(finished)
  assert.match(resultHtml, /first\.png.*已上傳.*retry\.jpg.*儲存暫時失敗.*last\.MOV.*已上傳/)
  assert.equal(demo.refetches(), 1)
  button(finished, '重試失敗檔案').props.onClick()
  await demo.result(0)
  assert.deepEqual(demo.posted.map(([, name]) => name), ['first.png', 'retry.jpg', 'last.MOV', 'retry.jpg'])
  assert.equal(button(demo.render(), '重試失敗檔案'), undefined)

  const sameFile = {value: first.name, files: [first]}
  input(demo.render()).props.onChange({currentTarget: sameFile})
  assert.equal(sameFile.value, '')
  button(demo.render(), '上傳到共用相簿').props.onClick()
  await demo.result(0)
  assert.equal(demo.posted.at(-1)[1], 'first.png')
}

async function testDeletion() {
  const demo = harness()
  const coach = demo.render()
  await demo.fetch()
  assert.equal(walk(coach, node => node.type === 'button' && /刪除相簿/.test(node.props['aria-label'])) .length, 1)
  const manager = demo.render(false)
  await demo.fetch()
  assert.deepEqual(demo.fetched, ['/coach/course-albums/23/', '/course-albums/23/'])
  assert.equal(input(manager), undefined)
  assert.equal(walk(manager, node => node.props['aria-pressed'] === true).length, 0)
  button(manager, '刪除').props.onClick()
  assert.match(demo.confirmed[0], /確定刪除這張照片/)
  assert.deepEqual(demo.removed, [])

  demo.acceptDelete()
  button(manager, '刪除').props.onClick()
  await demo.result(2)
  assert.deepEqual(demo.removed, [['/course-albums/23/', 51]])
  const failed = demo.render(false)
  assert.match(renderToStaticMarkup(failed), /暫時無法刪除相簿檔案/)
  button(failed, '刪除').props.onClick()
  await demo.result(2)
  const removed = demo.render(false)
  assert.equal(walk(removed, node => node.type === 'img').length, 0)
  assert.equal(walk(removed, node => node.type === 'video').length, 1)
  assert.match(renderToStaticMarkup(removed), /已刪除相簿附件/)
}

Promise.resolve().then(testUploads).then(testDeletion).catch(error => {
  console.error(error)
  process.exitCode = 1
})

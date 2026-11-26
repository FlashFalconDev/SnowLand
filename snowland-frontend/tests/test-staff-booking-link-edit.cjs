const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')

const compilerOptions = { jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS }
const readTsx = name => {
  const source = readFileSync(path.join(__dirname, '..', 'src', name), 'utf8')
  return ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
}
const run = (source, globals) => {
  const context = vm.createContext({ React, exports: {}, ...globals })
  vm.runInContext(ts.transpileModule(source, { compilerOptions }).outputText, context)
  return context
}
function findElement(tree, predicate) {
  if (React.isValidElement(tree)) {
    if (predicate(tree)) return tree
    return findElement(tree.props.children, predicate)
  }
  if (Array.isArray(tree)) {
    for (const child of tree) {
      const found = findElement(child, predicate)
      if (found) return found
    }
  }
}

const panelFile = readTsx('admin/pages/OperationsHubPage.tsx')
const panel = panelFile.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'BookingLinksPanel')
const cart = [{ id: 'g1', campusId: 1, peopleCount: 2, resortName: '測試雪場', courses: [{ courseTemplateName: '半天課', date: '2026-12-01' }] }]
const row = { id: 1, title: '半天課連結', can_edit: true, is_available: false, campus: 1, snapshot_version: 3, cart_snapshot: cart }
const unavailable = { ...row, id: 2, title: '已使用連結', can_edit: false, is_available: false }
const price = { previous_subtotal: 10000, subtotal: 12000, subtotal_difference: 2000, discount_total: 1000, total: 11000, previous_total: 9000, total_difference: 2000 }

async function checkConsole() {
  let preload
  let previewData
  let saved
  const render = editKey => {
    let mutationIndex = 0
    const context = run(panel.getText(panelFile), {
      useQueryClient: () => ({ invalidateQueries() {} }),
      useNotification: () => ({ success() {}, error() {} }),
      currentClientCode: () => 'snowland',
      useSearchParams: () => [new URLSearchParams(editKey ? { staff_edit: editKey } : {}), () => {}],
      useBookingStore: () => ({ cart: [], clearCart() {} }),
      getStaffBookingDraftStore: (tenant, key) => Object.assign(() => ({ cart, clearCart() {} }), {
        getState: () => ({ replaceCart(next) { preload = { tenant, key, cart: next } } }),
      }),
      useScopedCampuses: () => ({ campuses: [], selectedCampus: '' }),
      useQuery: () => ({ data: [row, unavailable] }),
      useState: value => [value, () => {}],
      useEffect() {},
      useMutation: options => {
        const index = mutationIndex++
        return {
          data: index === 1 ? previewData : undefined,
          mutate: async () => {
            const result = await options.mutationFn()
            if (index === 1) previewData = result
          },
        }
      },
      fetchStaffBookingLinks() {},
      previewStaffBookingLink: async (id, data) => {
        assert.equal(id, row.id)
        assert.equal(data.snapshot_version, 3)
        assert.equal(data.cart_snapshot, cart)
        return price
      },
      updateStaffBookingLink: async (id, data, quote) => { saved = { id, data, quote } },
      Link: ({ children }) => React.createElement('a', {}, children),
      Field: ({ children }) => React.createElement('label', {}, children),
      Plus: () => null,
      cardClass: 'card',
      inputClass: 'input',
      PRIMARY: '#123456',
    })
    return context.BookingLinksPanel()
  }
  const label = (tree, children) => findElement(tree, element => element.props.children === children)
  const list = render()
  const edit = label(list, '修改')
  assert.equal(edit.props.href, '/snowland/booking?staff_prepare=1&staff_edit=1%3A3')
  edit.props.onClick()
  assert.equal(preload.tenant, 'snowland')
  assert.equal(preload.key, '1:3')
  assert.equal(preload.cart[0].courses[0].courseTemplateName, '半天課')
  assert.doesNotMatch(renderToStaticMarkup(list), /staff_edit=2/)
  const before = render('1:3')
  assert.equal(label(before, '儲存修改').props.disabled, true)
  await label(before, '試算金額').props.onClick()
  const after = render('1:3')
  const html = renderToStaticMarkup(after)
  assert.match(html, /原試算金額 NT\$ 9,000/)
  assert.match(html, /新試算金額 NT\$ 11,000.*差額 \+2,000/)
  await label(after, '儲存修改').props.onClick()
  assert.equal(saved.id, row.id)
  assert.equal(saved.data.cart_snapshot, cart)
  assert.equal(saved.quote, price)
}

async function checkCustomerRefresh() {
  const file = readTsx('pages/BookingFlowPage.tsx')
  let conflict, load, submit
  const walk = node => {
    if (ts.isIfStatement(node) && node.expression.getText(file).includes("'staff_link_updated'")) conflict = node
    if (ts.isCallExpression(node) && node.expression.getText(file) === 'useEffect' &&
        node.arguments[0]?.getText(file).includes('resolveStaffBookingLink')) load = node
    if (ts.isCallExpression(node) && node.expression.getText(file) === 'createReservation') submit = node
    ts.forEachChild(node, walk)
  }
  walk(file)
  assert.match(submit.getText(file), /staff_link_version: staffLinkInfo\?\.snapshot_version/)
  let status, learnerChoices, pricePreview, revision = 0, loadedCart
  const token = 'synthetic-staff-link'
  const globals = {
    staffLinkToken: token,
    e: { response: { status: 409, data: { error: 'staff_link_updated' } } },
    setStaffLinkStatus(value) { status = value },
    setLearnerChoices(value) { learnerChoices = value },
    setDiscountPreviewResult(value) { pricePreview = value },
    setStaffLinkReloadKey(update) { revision = update(revision) },
  }
  run(`if (${conflict.expression.getText(file)}) ${conflict.thenStatement.getText(file)}`, globals)
  assert.equal(status, 'loading')
  assert.equal(Object.keys(learnerChoices).length, 0)
  assert.equal(pricePreview, null)
  assert.equal(revision, 1)
  const refreshed = [{ ...cart[0], totalPrice: 12000 }]
  run(load.getText(file), {
    ...globals,
    staffLinkReloadKey: revision,
    useEffect(effect, dependencies) {
      assert.ok(dependencies.includes(revision))
      effect()
    },
    setStaffLinkInfo() {},
    setCurrentStep(step) { assert.equal(step, 3) },
    resolveStaffBookingLink: async requestedToken => {
      assert.equal(requestedToken, token)
      return { snapshot_version: 4, cart_snapshot: refreshed }
    },
    replaceCart(next) { loadedCart = next },
  })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(loadedCart, refreshed)
  assert.equal(status, 'valid')
  assert.match(file.text, /內容已更新，請重新確認金額/)
}

Promise.all([checkConsole(), checkCustomerRefresh()]).then(() => {
  console.log('PASS staff edit previews and saves the scoped draft; stale customer cart reloads and retains the new version')
}).catch(error => { console.error(error); process.exitCode = 1 })

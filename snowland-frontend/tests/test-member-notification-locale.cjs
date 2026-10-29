const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), Module = require('node:module'), vm = require('node:vm')
const root = path.resolve(__dirname, '..'), req = Module.createRequire(path.join(root, 'package.json'))
const React = req('react'), ts = req('typescript'), { renderToStaticMarkup } = req('react-dom/server')
const source = fs.readFileSync(path.join(root, 'src/pages/site/MembershipPage.jsx'), 'utf8')
const extract = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))
const compiled = ts.transpileModule(extract('function MemberNotifications(', 'function MemberSection(') + extract('function CancellationForm(', 'function SharedClassSummary('), { fileName: 'member.jsx', compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 } }).outputText
function find(node, predicate) {
  if (!node || typeof node !== 'object') return null
  if (predicate(node)) return node
  for (const child of React.Children.toArray(node.props?.children)) { const result = find(child, predicate); if (result) return result }
  return null
}
async function main() {
  for (const language of ['en', 'ja']) {
    let states, cursor = 0
    const row = { id: 7, active: false, read_at: null, sent_at: '2026-10-19T13:00:00Z', subject: '私人通知標題QA', body: '私人通知內容QA', action_path: '/membership/orders/1', line_group_url: 'https://example.test/private' }
    const data = { results: [row], unread_count: 1, count: 1, page: 1, has_previous: false, has_next: false }
    const context = { React, useSiteLocale: require('./helpers/site-locale-harness.cjs')(React, language).useSiteLocale, useRef: () => ({ current: null }), useEffect() {}, useState() { const i = cursor++; return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value }] }, requestJson: async () => ({ read_at: '2026-10-19T14:00:00Z', unread_count: 0, message: '已標為已讀' }), SiteLink: ({ to, children }) => React.createElement('a', { href: to }, children), ClassGroupQRImage: () => null, EmptyState: ({ title }) => React.createElement('p', null, title), cancellationLabels: { requested: '取消審核中' }, refundMoney: () => 'JPY 1,000' }
    vm.runInNewContext(compiled, context)
    const renderNotifications = () => { cursor = 0; return context.MemberNotifications() }
    states = [1, data, false, '', null, null, '', 0]
    let tree = renderNotifications(), html = renderToStaticMarkup(tree)
    assert.ok(html.includes(language === 'en' ? 'No longer active' : '無効'))
    assert.ok(html.includes(new Date(row.sent_at).toLocaleString(language)))
    assert.ok(html.includes(row.subject) && html.includes(row.body), 'Private notification content stays unchanged')
    assert.ok(!html.includes('href='), 'Inactive notification never exposes stale action links')
    const markRead = find(tree, node => node.type === 'button')
    assert.equal(markRead.props.disabled, false)
    await markRead.props.onClick()
    tree = renderNotifications(); html = renderToStaticMarkup(tree)
    assert.ok(html.includes(language === 'en' ? 'Marked as read' : '既読にしました'))
    assert.equal(find(tree, node => node.type === 'button').props.disabled, true)
    states = [2, null, false, '這頁通知已不存在，請返回第一頁。', 404, null, '', 0]
    tree = renderNotifications(); html = renderToStaticMarkup(tree)
    assert.ok(!html.includes('這頁通知已不存在'))
    find(tree, node => node.type === 'button').props.onClick()
    assert.equal(states[0], 1); assert.equal(states[7], 1)
    states = [1, null, false, '請先登入', 401, null, '', 0]
    html = renderToStaticMarkup(renderNotifications())
    assert.ok(html.includes('/membership/notifications?login=1') && !html.includes('請先登入'))
    states = [{ request_status: 'requested', refund_amount: 1000 }, 'schedule', '', {}, '', false]; cursor = 0
    html = renderToStaticMarkup(context.CancellationForm({ order: { id: 1 }, onDone() {} }))
    assert.ok(html.includes(language === 'en' ? 'Current status: Cancellation under review' : '現在の状況：キャンセル審査中'))
    assert.ok(!html.includes('<select'), 'Pending cancellation cannot submit another request')
    console.log('PASS actual notification locale/read feedback/stale links/404/401 and cancellation status', language)
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })

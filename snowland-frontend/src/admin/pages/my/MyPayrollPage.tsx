import { useQuery } from '@tanstack/react-query'
import { fetchCoachPayroll } from '../../api/operations'
import PayrollReviewActions from '../../components/PayrollReviewActions'
import PayrollDocumentPanel from '../../components/PayrollDocumentPanel'
import { PayrollSettlementSummary } from '../../components/PayrollSettlementPanel'

const statuses: Record<string,string> = { review: '待我確認', confirmed: '已確認', paid: '已發放' }
export default function MyPayrollPage() {
  const query = useQuery({ queryKey:['coach','payroll'], queryFn:fetchCoachPayroll })
  return <div className="space-y-5"><h1 className="text-2xl font-bold text-gray-900 dark:text-white">我的薪資</h1><p className="text-sm text-gray-500 dark:text-gray-400">只顯示管理員已送出的本人薪資單。確認後可核對報酬單並上傳簽名；確認或簽署不代表已收到款項。</p>
    {query.isLoading ? <p>載入中…</p> : query.isError ? <div role="alert"><p>薪資資料載入失敗。</p><button className="min-h-11 text-violet-600 dark:text-violet-300" onClick={()=>void query.refetch()}>重新載入</button></div> : !query.data?.length ? <p className="rounded-xl bg-white p-6 dark:bg-gray-800">目前沒有已送交您的薪資單，未送出的草稿不會顯示。</p> : query.data.map(s=><section key={s.id} className="rounded-xl border border-gray-200 bg-white p-5 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100">
      <h2 className="font-semibold">{s.period_start}～{s.period_end} · {s.campus_name}</h2><p className="mt-2">狀態：{statuses[s.status] || s.status} · 扣款前台幣計薪合計 NT$ {s.total_amount.toLocaleString()}</p>
      <PayrollSettlementSummary snapshot={s.settlement_snapshot}/>
      <PayrollReviewActions key={`${s.id}-${s.review_token}-${s.status}`} statement={s} coachView />
      <PayrollDocumentPanel key={`document-${s.id}-${s.document_digest}-${s.signed_at}`} statement={s} coachView />
      <h3 className="mb-2 text-sm font-semibold">計算明細</h3><div className="space-y-2">{s.lines.map(line=><div key={line.id} className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700"><p className="break-words">{line.description.replace(/\bsnowboard\b/g,'單板').replace(/\bski\b/g,'雙板').replace(/\bphoto\b/g,'攝影')}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{line.line_type === 'referral' ? `${line.quantity}% × NT$ ${Number(line.unit_amount).toLocaleString()}` : `${line.quantity}${line.line_type === 'course' || line.line_type === 'assistance' ? ' 小時' : ' 項'} × NT$ ${Number(line.unit_amount).toLocaleString()}`} = NT$ {line.total_amount.toLocaleString()}</p></div>)}</div>
    </section>)}
  </div>
}

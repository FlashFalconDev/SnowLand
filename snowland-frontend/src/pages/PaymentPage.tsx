import { useState, useEffect } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { CheckCircle, CreditCard, Building2, Copy, Check, ArrowLeft } from 'lucide-react'
import LoadingOverlay from '@/components/ui/LoadingOverlay'
import Toast, { ToastType } from '@/components/ui/Toast'
import SettlementSummary, { settlementAmount, type OrderSettlement } from '@/components/booking/SettlementSummary'

const paymentHeaders = (): Record<string,string> => {
  const token=document.cookie.split(';').map(value=>value.trim()).find(value=>value.startsWith('csrftoken='))
  return {'Content-Type':'application/json',...(token?{'X-CSRFToken':token.slice('csrftoken='.length)}:{})}
}

const paymentError = (data: {error?:string;detail?:string}, fallback:string) => {
  const message=String(data.error || data.detail || fallback)
  return message.startsWith('CSRF Failed:') ? '頁面驗證已失效，請重新整理後再試；本次未送出。' : message
}

interface OrderDetail {
  pk: number
  course_label?: string
  course_fee: number
  coach_fee: number
  equipment_rental_fee: number
  equipment_assistance_time_label?: string
  language_fee: number
  discount_amount?: number
  discount_name?: string
  total_fee: number
}

interface PaymentData {
  settlement?: OrderSettlement
  reservation_group_id: number
  total_amount: number
  order_details: OrderDetail[]
  payment_status: string
  payment_methods?: string[]
  payment_expires_at?: string | null
  bank_info?: {
    bank_name?: string
    bank_branch?: string
    bank_account_number?: string
    bank_account_holder?: string
    overseas_details?: string
  }
}

export default function PaymentPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { clientCode = 'snowland' } = useParams<{ clientCode: string }>()
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [selectedMethod, setSelectedMethod] = useState<'newebpay' | 'bank_transfer'>('bank_transfer')
  const [senderAccount, setSenderAccount] = useState('')
  const [copied, setCopied] = useState(false)
  const [showLaterReminder, setShowLaterReminder] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '',
    type: 'info',
    isOpen: false
  })
  const [loadingMessage, setLoadingMessage] = useState('')

  const reservationGroupId = searchParams.get('reservation_group')
  const accessToken = searchParams.get('access_token') || ''
  const returnToOrders = () => navigate(`/${clientCode}/membership/orders${reservationGroupId ? `/${reservationGroupId}` : ''}`)
  const leavePayment = () => accessToken ? navigate(`/${clientCode}/`) : returnToOrders()
  const leaveLabel = accessToken ? '返回官網' : '返回我的訂單'
  const money = (amount: number) => amount.toLocaleString('zh-TW')

  const showToast = (message: string, type: ToastType = 'info') => {
    setToast({ message, type, isOpen: true })
  }

  useEffect(() => {
    if (!reservationGroupId) {
      showToast('缺少預約編號', 'error')
      navigate('..')
      return
    }

    // 從後端獲取付款資料
    const fetchPaymentData = async () => {
      try {
        const response = await fetch(
          `/booking/${encodeURIComponent(clientCode)}/api/payment-info/?${new URLSearchParams({ reservation_group: reservationGroupId, ...(accessToken ? { access_token: accessToken } : {}) })}`,
          {
            credentials: 'include', // 包含 session cookies
          }
        )
        const data = await response.json()

        if (!response.ok) {
          const message = paymentError(data,'獲取付款資訊失敗')
          setLoadError(message)
          showToast(message, 'error')
          setLoading(false)
          return
        }

        setLoadError('')
        setPaymentData(data)
        setSelectedMethod(data.payment_methods?.includes('bank_transfer') ? 'bank_transfer' : 'newebpay')
        setLoading(false)
      } catch (error) {
        setLoadError('無法連接到伺服器，請稍後再試')
        showToast('無法連接到伺服器', 'error')
        setLoading(false)
      }
    }

    fetchPaymentData()
  }, [reservationGroupId, accessToken, clientCode, navigate])

  const handleCopyAccount = () => {
    navigator.clipboard.writeText(paymentData?.bank_info?.bank_account_number || '')
    setCopied(true)
    showToast('已複製帳號', 'success')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleBankTransferLater = () => {
    const deadline = paymentData?.payment_expires_at
      ? new Date(paymentData.payment_expires_at).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })
      : '訂單付款期限'
    showToast(`請於 ${deadline} 前完成匯款；匯款後再回付款連結補後五碼。`, 'success')
    if (accessToken) setShowLaterReminder(true)
    else setTimeout(returnToOrders, 800)
  }

  const handleConfirmBankTransfer = async () => {
    if (!senderAccount || senderAccount.length !== 5) {
      showToast('請輸入正確的匯款帳戶後五碼', 'error')
      return
    }

    try {
      setLoadingMessage('提交匯款資訊中...')

      const response = await fetch(`/booking/${encodeURIComponent(clientCode)}/api/process-payment/`, {
        method: 'POST',
        headers: paymentHeaders(),
        credentials: 'include',
        body: JSON.stringify({
          reservation_group_id: reservationGroupId,
          payment_type: 'bank_transfer',
          sender_account: senderAccount,
            currency: paymentData?.settlement?.currency || 'TWD',
            expected_amount: paymentData?.settlement?.amount ?? paymentData?.total_amount,
          access_token: accessToken,
        })
      })

      const data = await response.json()

      if (!response.ok) {
        showToast(paymentError(data,'提交失敗'), 'error')
        setLoadingMessage('')
        return
      }

      showToast('匯款資訊已提交，請等待確認', 'success')
      setPaymentData(current => current ? { ...current, payment_status: 'pending' } : current)
      setLoadingMessage('')
      if (!accessToken) setTimeout(returnToOrders, 2000)
    } catch (error) {
      showToast('提交失敗，請稍後再試', 'error')
      setLoadingMessage('')
    }
  }

  const handleNewebpayPayment = async () => {
    try {
      setLoadingMessage('跳轉到付款頁面...')

      const response = await fetch(`/booking/${encodeURIComponent(clientCode)}/api/process-payment/`, {
        method: 'POST',
        headers: paymentHeaders(),
        credentials: 'include', // 包含 session cookies
        body: JSON.stringify({
          reservation_group_id: reservationGroupId,
          payment_type: 'newebpay',
          access_token: accessToken,
        })
      })

      const data = await response.json()

      if (!response.ok) {
        showToast(paymentError(data,'付款請求失敗'), 'error')
        setLoadingMessage('')
        return
      }

      // 藍新支付返回 HTML 表單，需要在新視窗中渲染並自動提交
      if (data.html) {
        // 創建新視窗並寫入 HTML
        const paymentWindow = window.open('', '_blank')
        if (paymentWindow) {
          paymentWindow.document.write(data.html)
          paymentWindow.document.close()
        } else {
          showToast('請允許彈出視窗以完成付款', 'warning')
        }
      }

      setLoadingMessage('')
    } catch (error) {
      showToast('跳轉失敗，請稍後再試', 'error')
      setLoadingMessage('')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f7f8fa] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-[#2b5f8f] border-r-transparent mb-4"></div>
          <p className="text-gray-600">載入付款資訊中...</p>
        </div>
      </div>
    )
  }

  if (!paymentData) {
    return <main className="flex min-h-screen items-center justify-center bg-[#f7f8fa] p-6">
      <div role="alert" className="w-full max-w-md rounded-sm border border-red-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">無法顯示付款資訊</h1>
        <p className="mt-3 text-sm text-red-700">{loadError || '請確認訂單連結是否正確。'}</p>
        <button onClick={leavePayment} className="mt-5 rounded-full bg-[#2b5f8f] px-5 py-2 font-semibold text-white">{leaveLabel}</button>
      </div>
    </main>
  }

  const canUseNewebpay = paymentData.payment_methods?.includes('newebpay') === true
  const canUseBankTransfer = paymentData.payment_methods?.includes('bank_transfer') === true
  const isPaid = paymentData.payment_status === 'paid'
  const isPending = paymentData.payment_status === 'pending'
  const isRefunded = paymentData.payment_status === 'refunded'
  const canSubmitPayment = paymentData.payment_status === 'unpaid'

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      {/* 頂部導航 */}
      <nav className="border-b border-[#dbe3ec] bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-[#1f2937] sm:text-2xl">
              課程付款
            </h1>
            <button
              onClick={leavePayment}
              className="flex items-center gap-2 whitespace-nowrap rounded-full border border-[#dbe3ec] bg-white px-4 py-2 text-sm font-semibold text-[#2b5f8f] transition-colors hover:bg-[#eef4fa]"
            >
              <ArrowLeft size={18} />
              <span>{leaveLabel}</span>
            </button>
          </div>
        </div>
      </nav>

      {/* 主要內容 */}
      <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        {/* 訂單摘要 */}
        <div className="mb-8 rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-sm sm:p-8">
          <h2 className="mb-6 text-2xl font-bold text-gray-800">訂單摘要</h2>

          <div className="space-y-4">
            {paymentData.order_details.map((item) => (
              <div key={item.pk} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 font-semibold text-gray-800">
                  {item.course_label || `預約課程 #${item.pk}`}
                </div>
                <div className="space-y-2 text-sm">
                  {item.course_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">課程費</span>
                      <span className="font-medium">NT$ {money(item.course_fee)}</span>
                    </div>
                  )}
                  {item.coach_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">教練費</span>
                      <span className="font-medium">NT$ {money(item.coach_fee)}</span>
                    </div>
                  )}
                  {item.equipment_rental_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">器材租借費</span>
                      <span className="font-medium">NT$ {money(item.equipment_rental_fee)}</span>
                    </div>
                  )}
                  {item.equipment_assistance_time_label && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">裝備協助時段</span>
                      <span className="font-medium">{item.equipment_assistance_time_label}</span>
                    </div>
                  )}
                  {item.language_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">語言服務費</span>
                      <span className="font-medium">NT$ {money(item.language_fee)}</span>
                    </div>
                  )}
                  {(item.discount_amount || 0) > 0 && (
                    <div className="flex justify-between text-emerald-700">
                      <span>{item.discount_name || '優惠折扣'}</span>
                      <span className="font-medium">− NT$ {money(item.discount_amount || 0)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <SettlementSummary settlement={paymentData.settlement} paymentInstructions={paymentData.payment_status==='unpaid'} />
          <div className="mt-6 flex items-center justify-between border-t-2 border-gray-200 pt-6">
            <span className="text-xl font-semibold text-gray-700">總金額</span>
            <span className="text-3xl font-bold text-[#2b5f8f]">
              {settlementAmount(paymentData.settlement,paymentData.total_amount)}
            </span>
          </div>
        </div>

        {isPaid && <div role="status" className="mb-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 font-semibold text-emerald-800">此訂單已付款，無需再次提交匯款資料。</div>}
        {isRefunded && <div role="status" className="mb-8 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 font-semibold text-[#1e4e73]">系統已記錄退款，不需再次付款。實際退款入帳請以銀行或金流紀錄為準。</div>}
        {!canSubmitPayment && !isPaid && !isPending && !isRefunded && <div role="status" className="mb-8 rounded-sm border border-amber-200 bg-amber-50 p-5 font-semibold text-amber-900">付款狀態已更新，請返回會員訂單確認；請勿再次匯款。</div>}
        {isPending && <div role="status" className="mb-8 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-5 font-semibold text-[#1e4e73]">匯款資料已送出，正在等待 SnowLand 確認付款；請勿重複匯款。如需更正匯款資料，請聯繫客服。{accessToken && <p className="mt-2 text-sm font-normal">請保留這個付款連結，之後可回來查看付款狀態。</p>}</div>}
        {showLaterReminder && canSubmitPayment && <div role="status" className="mb-8 rounded-sm border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">目前尚未回報匯款。請保留這個付款連結，在付款期限內完成匯款後，再回來填寫匯款帳戶後五碼。</div>}

        {/* 付款方式選擇 */}
        {canSubmitPayment && <div className="mb-8 rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-sm sm:p-8">
          <h2 className="mb-6 text-2xl font-bold text-gray-800">選擇付款方式</h2>

          <div className="grid gap-4 md:grid-cols-2">
            {/* 銀行匯款 */}
            {canUseBankTransfer && <button
              onClick={() => setSelectedMethod('bank_transfer')}
              className={`rounded-xl border-2 p-6 text-left transition-all ${
                selectedMethod === 'bank_transfer'
                  ? 'border-[#2b5f8f] bg-[#eaf4fb]'
                  : 'border-[#dbe3ec] bg-white hover:border-[#8eb5d2]'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${
                  selectedMethod === 'bank_transfer' ? 'bg-[#d7e9f5]' : 'bg-gray-200'
                }`}>
                  <Building2 size={24} className={selectedMethod === 'bank_transfer' ? 'text-[#2b5f8f]' : 'text-gray-600'} />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-800">銀行匯款</h3>
                  <p className="text-sm text-gray-600">匯款後等待確認</p>
                </div>
                {selectedMethod === 'bank_transfer' && (
                  <CheckCircle className="text-[#2b5f8f]" size={24} />
                )}
              </div>
            </button>}

            {/* 藍新支付 */}
            {canUseNewebpay && <button
              onClick={() => setSelectedMethod('newebpay')}
              className={`rounded-xl border-2 p-6 text-left transition-all ${
                selectedMethod === 'newebpay'
                  ? 'border-[#2b5f8f] bg-[#eaf4fb]'
                  : 'border-[#dbe3ec] bg-white hover:border-[#8eb5d2]'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${
                  selectedMethod === 'newebpay' ? 'bg-[#d7e9f5]' : 'bg-gray-200'
                }`}>
                  <CreditCard size={24} className={selectedMethod === 'newebpay' ? 'text-[#2b5f8f]' : 'text-gray-600'} />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-800">藍新支付</h3>
                  <p className="text-sm text-gray-600">信用卡/ATM/超商</p>
                </div>
                {selectedMethod === 'newebpay' && (
                  <CheckCircle className="text-[#2b5f8f]" size={24} />
                )}
              </div>
            </button>}
          </div>
          {!canUseBankTransfer && !canUseNewebpay && (
            <p role="alert" className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900">
              付款方式尚未設定完成，請聯繫客服協助，暫時不要匯款。
            </p>
          )}
        </div>}

        {/* 銀行匯款資訊 */}
        {canSubmitPayment && canUseBankTransfer && selectedMethod === 'bank_transfer' && (
          <div className="mb-8 rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-sm sm:p-8">
            <h2 className="mb-6 text-2xl font-bold text-gray-800">銀行匯款資訊</h2>

            <div className="mb-6 space-y-4 rounded-lg bg-blue-50 p-6">
              <div className="flex justify-between">
                <span className="text-gray-700">銀行名稱</span>
                <span className="font-semibold text-gray-900">{paymentData.bank_info?.bank_name || '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-700">分行名稱</span>
                <span className="font-semibold text-gray-900">{paymentData.bank_info?.bank_branch || '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">帳戶號碼</span>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900">{paymentData.bank_info?.bank_account_number || '—'}</span>
                  <button
                    onClick={handleCopyAccount}
                    disabled={!paymentData.bank_info?.bank_account_number}
                    className="rounded-lg bg-blue-100 p-2 transition-colors hover:bg-blue-200"
                    title="複製帳號"
                  >
                    {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} className="text-blue-600" />}
                  </button>
                </div>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-700">戶名</span>
                <span className="font-semibold text-gray-900">{paymentData.bank_info?.bank_account_holder || '—'}</span>
              </div>
              {paymentData.payment_expires_at && <div className="flex justify-between gap-3">
                <span className="shrink-0 text-gray-700">付款期限</span>
                <span className="text-right font-semibold text-gray-900">{new Date(paymentData.payment_expires_at).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false })}</span>
              </div>}
              {paymentData.bank_info?.overseas_details && <p className="whitespace-pre-wrap break-words text-sm text-gray-800">{paymentData.bank_info.overseas_details}</p>}
              <div className="flex justify-between border-t-2 border-blue-200 pt-4">
                <span className="text-lg font-bold text-gray-700">匯款金額</span>
                <span className="text-2xl font-bold text-[#2b5f8f]">
                  {settlementAmount(paymentData.settlement,paymentData.total_amount)}
                </span>
              </div>
            </div>

            <div className="mb-6">
              <label htmlFor="senderAccount" className="mb-2 block font-semibold text-gray-700">
                匯款帳戶後五碼（已匯款再填）
              </label>
              <input
                type="text"
                id="senderAccount"
                value={senderAccount}
                onChange={(e) => setSenderAccount(e.target.value.replace(/\D/g, '').slice(0, 5))}
                placeholder="請輸入您的匯款帳戶後五碼"
                maxLength={5}
                className="w-full rounded-sm border border-[#cbd5e1] px-4 py-3 focus:border-[#2b5f8f] focus:outline-none focus:ring-2 focus:ring-[#d7e9f5]"
              />
              <p className="mt-2 text-sm text-gray-600">
                若尚未匯款，可先按「稍後匯款」離開；完成匯款後再回付款連結填寫後五碼。
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                onClick={handleBankTransferLater}
                className="rounded-full border border-[#2b5f8f] bg-white px-8 py-4 text-lg font-bold text-[#2b5f8f] transition-colors hover:bg-[#eaf4fb]"
              >
                稍後匯款
              </button>
              <button
                onClick={handleConfirmBankTransfer}
                disabled={senderAccount.length !== 5}
                className="rounded-full bg-[#2b5f8f] px-8 py-4 text-lg font-bold text-white transition-colors hover:bg-[#1e4e73] disabled:cursor-not-allowed disabled:opacity-50"
              >
                確認已匯款
              </button>
            </div>
          </div>
        )}

        {/* 藍新支付 */}
        {canSubmitPayment && canUseNewebpay && selectedMethod === 'newebpay' && (
          <div className="mb-8 rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-sm sm:p-8">
            <h2 className="mb-6 text-2xl font-bold text-gray-800">藍新支付</h2>

            <div className="mb-6 rounded-sm bg-[#eaf4fb] p-6 text-center">
              <p className="mb-4 text-gray-700">
                點擊下方按鈕將跳轉到藍新金流付款頁面
              </p>
              <p className="text-lg font-bold text-[#2b5f8f]">
                付款金額：{settlementAmount(paymentData.settlement,paymentData.total_amount)}
              </p>
            </div>

            <button
              onClick={handleNewebpayPayment}
              className="w-full rounded-full bg-[#2b5f8f] px-8 py-4 text-lg font-bold text-white transition-colors hover:bg-[#1e4e73]"
            >
              前往付款
            </button>
          </div>
        )}
      </main>

      {/* Toast 通知 */}
      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={() => setToast({ ...toast, isOpen: false })}
      />

      {/* 載入動畫 */}
      <LoadingOverlay isLoading={!!loadingMessage} message={loadingMessage} />
    </div>
  )
}

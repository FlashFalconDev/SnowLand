import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle, CreditCard, Building2, Copy, Check, Home } from 'lucide-react'
import LoadingOverlay from '@/components/ui/LoadingOverlay'
import Toast, { ToastType } from '@/components/ui/Toast'

interface OrderDetail {
  pk: number
  course_fee: number
  coach_fee: number
  equipment_rental_fee: number
  equipment_assistance_time_label?: string
  language_fee: number
  total_fee: number
}

interface PaymentData {
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
  }
}

export default function PaymentPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedMethod, setSelectedMethod] = useState<'newebpay' | 'bank_transfer'>('bank_transfer')
  const [senderAccount, setSenderAccount] = useState('')
  const [copied, setCopied] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '',
    type: 'info',
    isOpen: false
  })
  const [loadingMessage, setLoadingMessage] = useState('')

  const reservationGroupId = searchParams.get('reservation_group')

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
          `/booking/snowland/api/payment-info/?reservation_group=${reservationGroupId}`,
          {
            credentials: 'include', // 包含 session cookies
          }
        )
        const data = await response.json()

        if (!response.ok) {
          showToast(data.error || '獲取付款資訊失敗', 'error')
          setLoading(false)
          return
        }

        setPaymentData(data)
        setLoading(false)
      } catch (error) {
        showToast('無法連接到伺服器', 'error')
        setLoading(false)
      }
    }

    fetchPaymentData()
  }, [reservationGroupId, navigate])

  const handleCopyAccount = () => {
    navigator.clipboard.writeText(paymentData?.bank_info?.bank_account_number || '')
    setCopied(true)
    showToast('已複製帳號', 'success')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleBankTransferLater = () => {
    showToast('訂單已保留 24 小時，請於期限內完成匯款；匯款後再回付款連結補後五碼。', 'success')
    setTimeout(() => navigate('..'), 800)
  }

  const handleConfirmBankTransfer = async () => {
    if (!senderAccount || senderAccount.length !== 5) {
      showToast('請輸入正確的匯款帳戶後五碼', 'error')
      return
    }

    try {
      setLoadingMessage('提交匯款資訊中...')

      const response = await fetch(`/booking/snowland/api/process-payment/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          reservation_group_id: reservationGroupId,
          payment_type: 'bank_transfer',
          sender_account: senderAccount
        })
      })

      const data = await response.json()

      if (!response.ok) {
        showToast(data.error || '提交失敗', 'error')
        setLoadingMessage('')
        return
      }

      showToast('匯款資訊已提交，請等待確認', 'success')
      setTimeout(() => {
        navigate('..')
      }, 2000)
    } catch (error) {
      showToast('提交失敗，請稍後再試', 'error')
      setLoadingMessage('')
    }
  }

  const handleNewebpayPayment = async () => {
    try {
      setLoadingMessage('跳轉到付款頁面...')

      const response = await fetch(`/booking/snowland/api/process-payment/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // 包含 session cookies
        body: JSON.stringify({
          reservation_group_id: reservationGroupId,
          payment_type: 'newebpay'
        })
      })

      const data = await response.json()

      if (!response.ok) {
        showToast(data.error || '付款請求失敗', 'error')
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

  if (loading || !paymentData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-primary-500 border-r-transparent mb-4"></div>
          <p className="text-gray-600">載入付款資訊中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      {/* 頂部導航 */}
      <nav className="bg-white/80 shadow-sm backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-primary-700">
              雪域滑雪課程預約 - 付款
            </h1>
            {(paymentData.payment_methods || ['bank_transfer', 'newebpay']).includes('newebpay') && <button
              onClick={() => navigate('..')}
              className="flex items-center gap-2 rounded-full bg-gray-200 px-4 py-2 text-gray-600 transition-all hover:bg-gray-300"
            >
              <Home size={20} />
              <span>返回首頁</span>
            </button>}
          </div>
        </div>
      </nav>

      {/* 主要內容 */}
      <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        {/* 訂單摘要 */}
        <div className="mb-8 rounded-3xl bg-white p-8 shadow-xl">
          <h2 className="mb-6 text-2xl font-bold text-gray-800">訂單摘要</h2>

          <div className="space-y-4">
            {paymentData.order_details.map((item) => (
              <div key={item.pk} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 font-semibold text-gray-800">
                  預約課程 {item.pk}
                </div>
                <div className="space-y-2 text-sm">
                  {item.course_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">課程費</span>
                      <span className="font-medium">NT$ {item.course_fee}</span>
                    </div>
                  )}
                  {item.coach_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">教練費</span>
                      <span className="font-medium">NT$ {item.coach_fee}</span>
                    </div>
                  )}
                  {item.equipment_rental_fee > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">器材租借費</span>
                      <span className="font-medium">NT$ {item.equipment_rental_fee}</span>
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
                      <span className="font-medium">NT$ {item.language_fee}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between border-t-2 border-gray-200 pt-6">
            <span className="text-xl font-semibold text-gray-700">總金額</span>
            <span className="text-3xl font-bold text-red-500">
              NT$ {paymentData.total_amount}
            </span>
          </div>
        </div>

        {/* 付款方式選擇 */}
        <div className="mb-8 rounded-3xl bg-white p-8 shadow-xl">
          <h2 className="mb-6 text-2xl font-bold text-gray-800">選擇付款方式</h2>

          <div className="grid gap-4 md:grid-cols-2">
            {/* 銀行匯款 */}
            <button
              onClick={() => setSelectedMethod('bank_transfer')}
              className={`rounded-xl border-2 p-6 text-left transition-all ${
                selectedMethod === 'bank_transfer'
                  ? 'border-primary-500 bg-primary-50 shadow-lg'
                  : 'border-gray-200 bg-white hover:border-primary-300'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${
                  selectedMethod === 'bank_transfer' ? 'bg-primary-200' : 'bg-gray-200'
                }`}>
                  <Building2 size={24} className={selectedMethod === 'bank_transfer' ? 'text-primary-600' : 'text-gray-600'} />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-800">銀行匯款</h3>
                  <p className="text-sm text-gray-600">匯款後等待確認</p>
                </div>
                {selectedMethod === 'bank_transfer' && (
                  <CheckCircle className="text-primary-500" size={24} />
                )}
              </div>
            </button>

            {/* 藍新支付 */}
            <button
              onClick={() => setSelectedMethod('newebpay')}
              className={`rounded-xl border-2 p-6 text-left transition-all ${
                selectedMethod === 'newebpay'
                  ? 'border-primary-500 bg-primary-50 shadow-lg'
                  : 'border-gray-200 bg-white hover:border-primary-300'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${
                  selectedMethod === 'newebpay' ? 'bg-primary-200' : 'bg-gray-200'
                }`}>
                  <CreditCard size={24} className={selectedMethod === 'newebpay' ? 'text-primary-600' : 'text-gray-600'} />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-800">藍新支付</h3>
                  <p className="text-sm text-gray-600">信用卡/ATM/超商</p>
                </div>
                {selectedMethod === 'newebpay' && (
                  <CheckCircle className="text-primary-500" size={24} />
                )}
              </div>
            </button>
          </div>
        </div>

        {/* 銀行匯款資訊 */}
        {selectedMethod === 'bank_transfer' && (
          <div className="mb-8 rounded-3xl bg-white p-8 shadow-xl">
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
              <div className="flex justify-between border-t-2 border-blue-200 pt-4">
                <span className="text-lg font-bold text-gray-700">匯款金額</span>
                <span className="text-2xl font-bold text-red-500">
                  NT$ {paymentData.total_amount}
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
                className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
              />
              <p className="mt-2 text-sm text-gray-600">
                若尚未匯款，可先按「稍後匯款」離開；完成匯款後再回付款連結填寫後五碼。
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                onClick={handleBankTransferLater}
                className="rounded-full border border-primary-500 bg-white px-8 py-4 text-lg font-bold text-primary-700 transition-all hover:bg-primary-50"
              >
                稍後匯款
              </button>
              <button
                onClick={handleConfirmBankTransfer}
                disabled={senderAccount.length !== 5}
                className="rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-8 py-4 text-lg font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
              >
                確認已匯款
              </button>
            </div>
          </div>
        )}

        {/* 藍新支付 */}
        {selectedMethod === 'newebpay' && (
          <div className="mb-8 rounded-3xl bg-white p-8 shadow-xl">
            <h2 className="mb-6 text-2xl font-bold text-gray-800">藍新支付</h2>

            <div className="mb-6 rounded-lg bg-purple-50 p-6 text-center">
              <p className="mb-4 text-gray-700">
                點擊下方按鈕將跳轉到藍新金流付款頁面
              </p>
              <p className="text-lg font-bold text-purple-600">
                付款金額：NT$ {paymentData.total_amount}
              </p>
            </div>

            <button
              onClick={handleNewebpayPayment}
              className="w-full rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-8 py-4 text-lg font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
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

import { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation, useParams } from 'react-router-dom'
import CourseCategoryModal from '@/components/booking/CourseCategoryModal'
import ResortModal from '@/components/booking/ResortModal'
import CourseTypeModal from '@/components/booking/CourseTypeModal'
import PeopleCountModal from '@/components/booking/PeopleCountModal'
import Under6QuestionModal from '@/components/booking/Under6QuestionModal'
import Under6SuggestModal from '@/components/booking/Under6SuggestModal'
import AbilityLevelModal from '@/components/booking/AbilityLevelModal'
import BookingStepsContainer from '@/components/booking/BookingStepsContainer'
import CartModal from '@/components/booking/CartModal'
import SchedulingFailedModal from '@/components/booking/SchedulingFailedModal'
import SuperScheduleConfirmModal from '@/components/booking/SuperScheduleConfirmModal'
import Toast, { ToastType } from '@/components/ui/Toast'
import LoadingOverlay from '@/components/ui/LoadingOverlay'
import LoginPage from '@/pages/LoginPage'
import AuthCallbackPage from '@/pages/AuthCallbackPage'
import PaymentPage from '@/pages/PaymentPage'
import HistoryPage from '@/pages/HistoryPage'
import ClientSelectionPage from '@/pages/ClientSelectionPage'
import SiteRoutes from '@/pages/site/SiteRoutes'
import { SiteBasePathContext } from '@/components/site/SiteLink'
// @ts-ignore
import SiteHeader from '@/components/site/SiteHeader'
// @ts-ignore
import SiteFooter from '@/components/site/SiteFooter'
import BookingFlowPage from '@/pages/BookingFlowPage'
import AdminRoutes from '@/admin/AdminRoutes'
import { ShoppingCart, User, LogOut, History, Award, Bot, Sliders } from 'lucide-react'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { createReservation, superSchedule } from '@/api/booking'

type ModalStep =
  | 'courseCategory'
  | 'resort'
  | 'courseType'
  | 'people'
  | 'under6Question'
  | 'under6Suggest'
  | 'ability'
  | 'booking'
  | 'none'

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [currentModal, setCurrentModal] = useState<ModalStep>('none')
  const [isInBookingFlow, setIsInBookingFlow] = useState(false)
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSchedulingFailedModalOpen, setIsSchedulingFailedModalOpen] = useState(false)
  const [schedulingFailedData, setSchedulingFailedData] = useState<{
    message: string
    conflictDetails?: any
  }>({ message: '' })
  const [isSuperScheduleConfirmOpen, setIsSuperScheduleConfirmOpen] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '',
    type: 'info',
    isOpen: false
  })
  const [loadingMessage, setLoadingMessage] = useState('')
  const cart = useBookingStore((state) => state.cart)
  const clearCart = useBookingStore((state) => state.clearCart)
  const peopleCount = useBookingStore((state) => state.peopleCount)
  const hasUnder6 = useBookingStore((state) => state.hasUnder6)
  const setPeopleCount = useBookingStore((state) => state.setPeopleCount)
  const { user, loading, logout } = useAuth()

  // 顯示 Toast 通知
  const showToast = (message: string, type: ToastType = 'info') => {
    setToast({ message, type, isOpen: true })
  }

  // 處理進階排課
  const handleSuperSchedule = async () => {
    if (cart.length === 0) {
      showToast('購物車是空的', 'warning')
      return
    }

    if (isSubmitting) return

    try {
      setIsSubmitting(true)
      setLoadingMessage('進階排課處理中...')

      // 調用進階排課API
      const response = await superSchedule({ cart })

      if (response.code === 200) {
        if (response.requires_payment && response.payment_url) {
          showToast('預約成功！正在跳轉到付款頁面...', 'success')
          clearCart()
          setIsCartOpen(false)
          // 從 payment_url 提取 reservation_group 參數
          const urlParams = new URLSearchParams(response.payment_url.split('?')[1])
          const reservationGroup = urlParams.get('reservation_group')
          setTimeout(() => {
            navigate(`/payment?reservation_group=${reservationGroup}`)
          }, 1500)
        } else if (response.scheduling_failed) {
          // 即使進階排課也失敗
          showToast('進階排課失敗，請調整課程日期或時段，或聯繫客服人工安排', 'error')
        } else {
          showToast(response.msg, 'success')
          clearCart()
          setIsCartOpen(false)
        }
      } else {
        showToast(`進階排課失敗：${response.msg}`, 'error')
      }
    } catch (error: any) {
      console.error('進階排課失敗:', error)
      showToast(`進階排課失敗：${error.response?.data?.msg || error.message || '未知錯誤'}`, 'error')
    } finally {
      setIsSubmitting(false)
      setLoadingMessage('')
    }
  }

  // 處理預約確認
  const handleConfirmReservation = async () => {
    if (cart.length === 0) {
      showToast('購物車是空的', 'warning')
      return
    }

    if (isSubmitting) return

    try {
      setIsSubmitting(true)
      setLoadingMessage('預約處理中...')

      // 調用API創建預約
      const response = await createReservation({ cart })

      if (response.code === 200) {
        // 檢查是否需要付款
        if (response.requires_payment) {
          if (response.payment_url) {
            // 單一預約組，直接跳轉到付款頁面
            showToast('預約成功！正在跳轉到付款頁面...', 'success')
            clearCart()
            setIsCartOpen(false)
            // 從 payment_url 提取 reservation_group 參數
            const urlParams = new URLSearchParams(response.payment_url.split('?')[1])
            const reservationGroup = urlParams.get('reservation_group')
            setTimeout(() => {
              navigate(`/payment?reservation_group=${reservationGroup}`)
            }, 1500)
          } else if (response.payment_urls && response.payment_urls.length > 0) {
            // 多個預約組，暫時跳轉到第一個
            // TODO: 未來可以實現一個選擇頁面讓用戶選擇要付款哪個預約
            showToast(`預約成功！已創建 ${response.reservation_group_ids.length} 個預約，正在跳轉到付款頁面...`, 'success')
            clearCart()
            setIsCartOpen(false)
            const urlParams = new URLSearchParams(response.payment_urls[0].payment_url.split('?')[1])
            const reservationGroup = urlParams.get('reservation_group')
            setTimeout(() => {
              navigate(`/payment?reservation_group=${reservationGroup}`)
            }, 1500)
          }
        } else {
          // 不需要付款（例如排課失敗等情況）
          if (response.scheduling_failed) {
            // 排課失敗，打開排課失敗Modal
            setSchedulingFailedData({
              message: response.msg,
              conflictDetails: response.conflict_details
            })
            setIsSchedulingFailedModalOpen(true)
            setIsCartOpen(false)
            // 排課失敗不清空購物車，讓用戶可以修改
          } else {
            showToast(response.msg, 'info')
            clearCart()
            setIsCartOpen(false)
          }
        }
      } else {
        showToast(`預約失敗：${response.msg}`, 'error')
      }
    } catch (error: any) {
      console.error('預約失敗:', error)
      showToast(`預約失敗：${error.response?.data?.msg || error.message || '未知錯誤'}`, 'error')
    } finally {
      setIsSubmitting(false)
      setLoadingMessage('')
    }
  }

  // 如果正在加載，顯示loading
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-primary-500 border-r-transparent mb-4"></div>
          <p className="text-gray-600">載入中...</p>
        </div>
      </div>
    )
  }

  // 路由處理
  return (
    <Routes>
      {/* 🔥 客戶選擇頁面（Landing Page） */}
      <Route path="/" element={<ClientSelectionPage />} />

      {/* OAuth callback 頁面 */}
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      {/* 🔥 多租戶路由：/:clientCode/xxx */}
      <Route path="/:clientCode/*" element={<ClientRoutes />} />
    </Routes>
  )
}

// 🔥 客戶專屬路由組件
function ClientRoutes() {
  const { clientCode } = useParams<{ clientCode: string }>()

  useEffect(() => {
    // 儲存 client_code 到 localStorage
    if (clientCode) {
      localStorage.setItem('client_code', clientCode)
    }
  }, [clientCode])

  const basePath = clientCode ? `/${clientCode}` : ''

  return (
    <SiteBasePathContext.Provider value={basePath}>
      <Routes>
        {/* 付款頁面 */}
        <Route path="payment" element={<PaymentPage />} />

        {/* 歷史紀錄頁面 */}
        <Route path="history" element={<HistoryPage />} />

        {/* 預約系統 — 官網風格 4 步流程（整合版） */}
        <Route path="booking" element={<BookingFlowPage />} />
        <Route path="booking/*" element={<BookingFlowPage />} />

        {/* 管理後台 — 給滑雪學校自己用 */}
        <Route path="console/*" element={<AdminRoutes />} />

        {/* 舊版預約系統（Modal 流程），保留備用 */}
        <Route path="booking-legacy" element={<MainApp />} />
        <Route path="booking-legacy/*" element={<MainApp />} />

        {/* 官網頁面（公開） */}
        <Route path="*" element={<SiteRoutes />} />
      </Routes>
    </SiteBasePathContext.Provider>
  )
}

// 主應用組件
function MainApp() {
  const navigate = useNavigate()
  const [currentModal, setCurrentModal] = useState<ModalStep>('none')
  const [isInBookingFlow, setIsInBookingFlow] = useState(false)
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSchedulingFailedModalOpen, setIsSchedulingFailedModalOpen] = useState(false)
  const [schedulingFailedData, setSchedulingFailedData] = useState<{
    message: string
    conflictDetails?: any
  }>({ message: '' })
  const [isSuperScheduleConfirmOpen, setIsSuperScheduleConfirmOpen] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '',
    type: 'info',
    isOpen: false
  })
  const [loadingMessage, setLoadingMessage] = useState('')
  const cart = useBookingStore((state) => state.cart)
  const clearCart = useBookingStore((state) => state.clearCart)
  const peopleCount = useBookingStore((state) => state.peopleCount)
  const hasUnder6 = useBookingStore((state) => state.hasUnder6)
  const setPeopleCount = useBookingStore((state) => state.setPeopleCount)
  const { user, loading, logout } = useAuth()

  // 顯示 Toast 通知
  const showToast = (message: string, type: ToastType = 'info') => {
    setToast({ message, type, isOpen: true })
  }

  // 處理進階排課
  const handleSuperSchedule = async () => {
    if (cart.length === 0) {
      showToast('購物車是空的', 'warning')
      return
    }

    if (isSubmitting) return

    try {
      setIsSubmitting(true)
      setLoadingMessage('進階排課處理中...')

      // 調用進階排課API
      const response = await superSchedule({ cart })

      if (response.code === 200) {
        if (response.requires_payment && response.payment_url) {
          showToast('預約成功！正在跳轉到付款頁面...', 'success')
          clearCart()
          setIsCartOpen(false)
          // 從 payment_url 提取 reservation_group 參數
          const urlParams = new URLSearchParams(response.payment_url.split('?')[1])
          const reservationGroup = urlParams.get('reservation_group')
          setTimeout(() => {
            navigate(`/payment?reservation_group=${reservationGroup}`)
          }, 1500)
        } else if (response.scheduling_failed) {
          // 即使進階排課也失敗
          showToast('進階排課失敗，請調整課程日期或時段，或聯繫客服人工安排', 'error')
        } else {
          showToast(response.msg, 'success')
          clearCart()
          setIsCartOpen(false)
        }
      } else {
        showToast(`進階排課失敗：${response.msg}`, 'error')
      }
    } catch (error: any) {
      console.error('進階排課失敗:', error)
      showToast(`進階排課失敗：${error.response?.data?.msg || error.message || '未知錯誤'}`, 'error')
    } finally {
      setIsSubmitting(false)
      setLoadingMessage('')
    }
  }

  // 處理預約確認
  const handleConfirmReservation = async () => {
    if (cart.length === 0) {
      showToast('購物車是空的', 'warning')
      return
    }

    if (isSubmitting) return

    try {
      setIsSubmitting(true)
      setLoadingMessage('預約處理中...')

      // 調用API創建預約
      const response = await createReservation({ cart })

      if (response.code === 200) {
        // 檢查是否需要付款
        if (response.requires_payment) {
          if (response.payment_url) {
            // 單一預約組，直接跳轉到付款頁面
            showToast('預約成功！正在跳轉到付款頁面...', 'success')
            clearCart()
            setIsCartOpen(false)
            // 從 payment_url 提取 reservation_group 參數
            const urlParams = new URLSearchParams(response.payment_url.split('?')[1])
            const reservationGroup = urlParams.get('reservation_group')
            setTimeout(() => {
              navigate(`/payment?reservation_group=${reservationGroup}`)
            }, 1500)
          } else if (response.payment_urls && response.payment_urls.length > 0) {
            // 多個預約組，暫時跳轉到第一個
            // TODO: 未來可以實現一個選擇頁面讓用戶選擇要付款哪個預約
            showToast(`預約成功！已創建 ${response.reservation_group_ids.length} 個預約，正在跳轉到付款頁面...`, 'success')
            clearCart()
            setIsCartOpen(false)
            const urlParams = new URLSearchParams(response.payment_urls[0].payment_url.split('?')[1])
            const reservationGroup = urlParams.get('reservation_group')
            setTimeout(() => {
              navigate(`/payment?reservation_group=${reservationGroup}`)
            }, 1500)
          }
        } else {
          // 不需要付款（例如排課失敗等情況）
          if (response.scheduling_failed) {
            // 排課失敗，打開排課失敗Modal
            setSchedulingFailedData({
              message: response.msg,
              conflictDetails: response.conflict_details
            })
            setIsSchedulingFailedModalOpen(true)
            setIsCartOpen(false)
            // 排課失敗不清空購物車，讓用戶可以修改
          } else {
            showToast(response.msg, 'info')
            clearCart()
            setIsCartOpen(false)
          }
        }
      } else {
        showToast(`預約失敗：${response.msg}`, 'error')
      }
    } catch (error: any) {
      console.error('預約失敗:', error)
      showToast(`預約失敗：${error.response?.data?.msg || error.message || '未知錯誤'}`, 'error')
    } finally {
      setIsSubmitting(false)
      setLoadingMessage('')
    }
  }

  // 如果未登入，顯示登入頁面（包裹在官網外殼中）
  if (!user) {
    return (
      <div className="w-full font-sans">
        <SiteHeader forceTransparent={false} forceDarkText={true} forceLogoColor={true} hideBookingCta={true} />
        <div className="pt-24">
          <LoginPage />
        </div>
        <SiteFooter />
      </div>
    )
  }

  const handlePeopleConfirm = (count: number, hasUnder6: boolean) => {
    if (hasUnder6 && count > 1) {
      setCurrentModal('under6Question')
    } else {
      setCurrentModal('ability')
    }
  }

  // 預約系統主頁面 — 使用官網的 SiteHeader/SiteFooter
  return (
    <div className="w-full font-sans">
      <SiteHeader
        forceTransparent={false}
        forceDarkText={true}
        forceLogoColor={true}
        memberAuthenticated={true}
        memberAvatarSrc={user.picture || ''}
        hideBookingCta={true}
      />

      {/* 預約系統內容 */}
      <div className="pt-20 min-h-screen bg-[#f7f8fa]">

        {isInBookingFlow ? (
          <>
            {/* 預約流程進行中 — 步驟選擇 */}
            <div className="max-w-6xl mx-auto px-6 md:px-10 py-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-semibold text-[#1f2937] font-display">課程預約</h2>
                <button
                  onClick={() => setIsCartOpen(true)}
                  className="relative inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#1f4a6f] transition-colors"
                >
                  <ShoppingCart size={18} className="mr-2" />
                  購物車
                  {cart.length > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-brand-orange text-xs font-bold text-white">
                      {cart.length}
                    </span>
                  )}
                </button>
              </div>

              <BookingStepsContainer
                onClose={() => {
                  setIsInBookingFlow(false)
                  setCurrentModal('none')
                }}
                onComplete={() => {
                  setIsInBookingFlow(false)
                  setCurrentModal('none')
                }}
              />
            </div>
          </>
        ) : (
          <>
            {/* 預約起始頁 — 官網風格 */}
            <div className="max-w-4xl mx-auto px-6 md:px-10 py-16 md:py-24">
              <div className="text-center mb-12">
                <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
                  Booking
                </p>
                <h2 className="text-2xl md:text-3xl font-semibold text-[#1f2937] mt-4 font-display">
                  課程預約
                </h2>
                <p className="mt-4 text-sm text-[#6b7280] leading-relaxed">
                  跟隨步驟完成課程預約，我們將為您安排最適合的教練與時段
                </p>
              </div>

              {/* 步驟說明卡片 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                {[
                  { num: '01', title: '選擇課程', desc: '選擇課程大類、雪場、類型與人數' },
                  { num: '02', title: '安排細節', desc: '選擇教練、裝備、日期與時段' },
                  { num: '03', title: '確認付款', desc: '確認訂單內容並完成付款' },
                ].map((step) => (
                  <div
                    key={step.num}
                    className="bg-white border border-[#e5e9f2] rounded-sm p-8 text-center"
                  >
                    <p className="text-3xl font-bold text-[#2b5f8f] font-display">{step.num}</p>
                    <h3 className="mt-4 text-base font-semibold text-[#1f2937] font-display">{step.title}</h3>
                    <p className="mt-2 text-sm text-[#6b7280] leading-relaxed">{step.desc}</p>
                  </div>
                ))}
              </div>

              {/* 開始預約按鈕 */}
              <div className="text-center">
                <button
                  onClick={() => setCurrentModal('courseCategory')}
                  className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-10 py-4 text-base font-semibold text-white hover:bg-[#1f4a6f] transition-colors shadow-lg hover:shadow-xl"
                >
                  開始預約
                  <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </div>

              {/* 購物車快捷 */}
              {cart.length > 0 && (
                <div className="mt-8 text-center">
                  <button
                    onClick={() => setIsCartOpen(true)}
                    className="inline-flex items-center justify-center rounded-full border border-[#2b5f8f] px-6 py-3 text-sm font-semibold text-[#2b5f8f] hover:bg-[#2b5f8f] hover:text-white transition-colors"
                  >
                    <ShoppingCart size={16} className="mr-2" />
                    查看購物車（{cart.length} 項）
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <SiteFooter />

      {/* === Modals === */}
      <CourseCategoryModal
        isOpen={currentModal === 'courseCategory'}
        onClose={() => setCurrentModal('none')}
        onNext={() => setCurrentModal('resort')}
      />

      <ResortModal
        isOpen={currentModal === 'resort'}
        onClose={() => setCurrentModal('none')}
        onNext={() => setCurrentModal('courseType')}
        onBack={() => setCurrentModal('courseCategory')}
      />

      <CourseTypeModal
        isOpen={currentModal === 'courseType'}
        onClose={() => setCurrentModal('none')}
        onNext={() => setCurrentModal('people')}
        onBack={() => setCurrentModal('resort')}
      />

      <PeopleCountModal
        isOpen={currentModal === 'people'}
        onClose={() => setCurrentModal('none')}
        onNext={handlePeopleConfirm}
        onBack={() => setCurrentModal('courseType')}
      />

      <Under6QuestionModal
        isOpen={currentModal === 'under6Question'}
        onClose={() => setCurrentModal('none')}
        onCanSelfSki={() => setCurrentModal('ability')}
        onCannotSelfSki={() => setCurrentModal('under6Suggest')}
        onBack={() => setCurrentModal('people')}
      />

      <Under6SuggestModal
        isOpen={currentModal === 'under6Suggest'}
        onClose={() => setCurrentModal('none')}
        onConfirm={() => {
          setPeopleCount(1)
          setCurrentModal('people')
        }}
        onBack={() => setCurrentModal('under6Question')}
      />

      <AbilityLevelModal
        isOpen={currentModal === 'ability'}
        onClose={() => setCurrentModal('none')}
        onNext={() => {
          setCurrentModal('none')
          setIsInBookingFlow(true)
        }}
        onBack={() => {
          if (hasUnder6 && peopleCount === 1) {
            setCurrentModal('under6Suggest')
          } else if (hasUnder6) {
            setCurrentModal('under6Question')
          } else {
            setCurrentModal('people')
          }
        }}
      />

      <CartModal
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        onConfirm={handleConfirmReservation}
      />

      <SchedulingFailedModal
        isOpen={isSchedulingFailedModalOpen}
        onClose={() => {
          setIsSchedulingFailedModalOpen(false)
          setIsCartOpen(true)
        }}
        onTrySuperSchedule={() => {
          setIsSchedulingFailedModalOpen(false)
          setIsSuperScheduleConfirmOpen(true)
        }}
        message={schedulingFailedData.message}
        conflictDetails={schedulingFailedData.conflictDetails}
      />

      <SuperScheduleConfirmModal
        isOpen={isSuperScheduleConfirmOpen}
        onClose={() => setIsSuperScheduleConfirmOpen(false)}
        onConfirm={async () => {
          setIsSuperScheduleConfirmOpen(false)
          await handleSuperSchedule()
        }}
      />

      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={() => setToast({ ...toast, isOpen: false })}
      />

      <LoadingOverlay isLoading={!!loadingMessage} message={loadingMessage} />
    </div>
  )
}

export default App

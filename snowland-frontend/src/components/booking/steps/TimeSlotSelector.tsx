import { useState, useEffect } from 'react'
import { useBookingStore } from '@/store/bookingStore'
import { fetchCourseSessions, calculatePrice } from '@/api/booking'
import { Course, CourseSession } from '@/types/booking'
import { Clock, CheckCircle, Plus, ShoppingCart } from 'lucide-react'
import Toast from '@/components/ui/Toast'
import { useToast } from '@/hooks/useToast'

interface TimeSlotSelectorProps {
  onNext: () => void
  onBack: () => void
  onComplete: () => void // 完成並加入購物車
  goToStep: (step: 1 | 2 | 3 | 4 | 5) => void
}

export default function TimeSlotSelector({
  onNext,
  onBack,
  onComplete,
  goToStep,
}: TimeSlotSelectorProps) {
  const [sessions, setSessions] = useState<CourseSession[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null)
  const [isCalculatingPrice, setIsCalculatingPrice] = useState(false)
  const { toast, hideToast, error: showError, success: showSuccess } = useToast()

  const bookingState = useBookingStore((state) => ({
    selectedCourseTemplate: state.selectedCourseTemplate,
    selectedDate: state.selectedDate,
    selectedCourseType: state.selectedCourseType,
    selectedResort: state.selectedResort,
    peopleCount: state.peopleCount,
    selectedAbilityLevel: state.selectedAbilityLevel,
    needEquipment: state.needEquipment,
  }))

  const setSelectedTimeSlot = useBookingStore((state) => state.setSelectedTimeSlot)
  const addCourseToCurrentGroup = useBookingStore((state) => state.addCourseToCurrentGroup)
  const finishCurrentGroupAndAddToCart = useBookingStore(
    (state) => state.finishCurrentGroupAndAddToCart
  )
  const resetStepSelection = useBookingStore((state) => state.resetStepSelection)

  useEffect(() => {
    const loadSessions = async () => {
      if (!bookingState.selectedCourseTemplate) return

      try {
        setLoading(true)
        setError(null)
        const data = await fetchCourseSessions(bookingState.selectedCourseTemplate)
        setSessions(data)
      } catch (err) {
        console.error('載入時段列表失敗:', err)
        setError('載入時段列表失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    loadSessions()
  }, [bookingState.selectedCourseTemplate])

  const formatTime = (time: string) => {
    // 將 HH:MM:SS 格式轉換為 HH:MM
    return time.substring(0, 5)
  }

  const handleTimeSlotClick = (sessionId: number) => {
    setSelectedSessionId(sessionId)
    setSelectedTimeSlot(sessionId)
  }

  const createCourseFromSelection = async (): Promise<Course> => {
    const selectedSession = sessions.find((s) => s.id === selectedSessionId)
    if (!selectedSession) throw new Error('未選擇時段')

    // 調用API計算價格
    const priceData = await calculatePrice({
      template_id: bookingState.selectedCourseTemplate || 0,
      resort: bookingState.selectedResort || '',
      people_count: bookingState.peopleCount,
      course_date: bookingState.selectedDate || '',
    })

    return {
      date: bookingState.selectedDate || '',
      courseTypeId: bookingState.selectedCourseType || 0,
      courseTypeName: priceData.course_type_name || '課程',
      courseTemplateId: bookingState.selectedCourseTemplate || 0,
      courseTemplateName: priceData.course_template_name || '課程模板',
      durationHours: priceData.duration_hours || 0,
      timeSlotId: selectedSessionId!,
      timeSlotStart: selectedSession.start_time,
      timeSlotEnd: selectedSession.end_time,
      price: priceData.price,
    }
  }

  const handleContinueAdding = async () => {
    if (!selectedSessionId) return

    // 檢查是否有重複的日期+時段
    const currentGroup = useBookingStore.getState().currentReservationGroup
    if (currentGroup) {
      const selectedSession = sessions.find((s) => s.id === selectedSessionId)
      const isDuplicate = currentGroup.courses.some(
        (course) =>
          course.date === bookingState.selectedDate &&
          course.timeSlotId === selectedSessionId
      )

      if (isDuplicate) {
        showError(
          `同一個預約中不能選擇相同的日期和時段！已選擇：${bookingState.selectedDate} ${selectedSession?.start_time} - ${selectedSession?.end_time}。請選擇不同的日期或時段。`,
          5000
        )
        return
      }
    }

    try {
      setIsCalculatingPrice(true)
      const course = await createCourseFromSelection()
      addCourseToCurrentGroup(course)
      showSuccess('✓ 課程已加入，可繼續選擇更多課程！', 2000)

      // 重置步驟選擇，回到 Step 3（選擇課程模板）
      resetStepSelection()
      setSelectedSessionId(null)
      goToStep(3) // 跳回選擇課程模板
    } catch (err) {
      console.error('加入課程失敗:', err)
      showError('加入課程失敗，請檢查網路連線或稍後再試', 4000)
    } finally {
      setIsCalculatingPrice(false)
    }
  }

  const handleFinishAndAddToCart = async () => {
    if (!selectedSessionId) return

    // 檢查是否有重複的日期+時段
    const currentGroup = useBookingStore.getState().currentReservationGroup
    if (currentGroup) {
      const selectedSession = sessions.find((s) => s.id === selectedSessionId)
      const isDuplicate = currentGroup.courses.some(
        (course) =>
          course.date === bookingState.selectedDate &&
          course.timeSlotId === selectedSessionId
      )

      if (isDuplicate) {
        showError(
          `同一個預約中不能選擇相同的日期和時段！已選擇：${bookingState.selectedDate} ${selectedSession?.start_time} - ${selectedSession?.end_time}。請選擇不同的日期或時段。`,
          5000
        )
        return
      }
    }

    try {
      setIsCalculatingPrice(true)
      const course = await createCourseFromSelection()
      addCourseToCurrentGroup(course)

      // 完成預約組並加入購物車
      finishCurrentGroupAndAddToCart()

      // 通知完成
      onComplete()
    } catch (err) {
      console.error('加入購物車失敗:', err)
      showError('加入購物車失敗，請檢查網路連線或稍後再試', 4000)
    } finally {
      setIsCalculatingPrice(false)
    }
  }

  const selectedSession = sessions.find((s) => s.id === selectedSessionId)

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-2xl font-bold text-gray-800">選擇上課時段</h3>
        <p className="mt-2 text-gray-600">請選擇您想要的上課時間</p>
      </div>

      {loading && (
        <div className="py-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">載入時段列表中...</p>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-600">{error}</div>
      )}

      {!loading && !error && sessions.length === 0 && (
        <div className="flex flex-col items-center gap-6 py-12">
          <div className="rounded-lg bg-yellow-50 px-6 py-4 text-center">
            <p className="text-lg font-medium text-yellow-800">
              😔 目前沒有可用的上課時段
            </p>
            <p className="mt-2 text-sm text-yellow-700">
              請返回重新選擇課程模板或日期
            </p>
          </div>
          <button
            onClick={onBack}
            className="rounded-lg bg-primary-500 px-8 py-3 text-lg font-semibold text-white transition-all duration-300 hover:bg-primary-600 hover:shadow-lg"
          >
            ← 返回上一步
          </button>
        </div>
      )}

      {!loading && !error && sessions.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => handleTimeSlotClick(session.id)}
                className={`group relative overflow-hidden rounded-2xl border-2 p-6 text-left transition-all hover:scale-105 hover:shadow-xl ${
                  selectedSessionId === session.id
                    ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-purple-50'
                    : 'border-gray-200 bg-gradient-to-br from-white to-primary-50 hover:border-primary-500'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`flex h-16 w-16 items-center justify-center rounded-full shadow-lg ${
                      selectedSessionId === session.id
                        ? 'bg-gradient-to-br from-primary-500 to-purple-500'
                        : 'bg-gradient-to-br from-primary-400 to-purple-400'
                    } text-white`}
                  >
                    <Clock size={32} />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-2xl font-bold text-gray-800">
                      {formatTime(session.start_time)} -{' '}
                      {formatTime(session.end_time)}
                    </h3>
                    <p className="mt-1 text-sm text-gray-600">
                      {selectedSessionId === session.id
                        ? '✓ 已選擇此時段'
                        : '點擊選擇此時段'}
                    </p>
                  </div>
                  <CheckCircle
                    size={24}
                    className={`transition-colors ${
                      selectedSessionId === session.id
                        ? 'text-primary-500'
                        : 'text-gray-300 group-hover:text-primary-500'
                    }`}
                  />
                </div>
                <div className="absolute -right-8 -bottom-8 h-32 w-32 rounded-full bg-primary-200/20 transition-all group-hover:scale-150" />
              </button>
            ))}
          </div>

          {selectedSessionId && selectedSession && (
            <div className="mt-8 space-y-4">
              {/* 選擇確認提示 */}
              <div className="rounded-lg bg-gradient-to-r from-primary-100 to-purple-100 p-4">
                <p className="text-center font-semibold text-gray-800">
                  ✓ 已選擇時段：{formatTime(selectedSession.start_time)} -{' '}
                  {formatTime(selectedSession.end_time)}
                </p>
              </div>

              {/* 兩個按鈕 */}
              <div className="flex gap-4">
                <button
                  onClick={handleContinueAdding}
                  disabled={isCalculatingPrice}
                  className="flex flex-1 items-center justify-center gap-2 rounded-full border-2 border-primary-500 bg-white px-6 py-4 font-bold text-primary-600 transition-all hover:bg-primary-50 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isCalculatingPrice ? (
                    <>
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
                      <span>計算價格中...</span>
                    </>
                  ) : (
                    <>
                      <Plus size={20} />
                      <span>繼續新增課程</span>
                    </>
                  )}
                </button>

                <button
                  onClick={handleFinishAndAddToCart}
                  disabled={isCalculatingPrice}
                  className="flex flex-1 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-6 py-4 font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isCalculatingPrice ? (
                    <>
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      <span>計算價格中...</span>
                    </>
                  ) : (
                    <>
                      <ShoppingCart size={20} />
                      <span>完成並加入購物車</span>
                    </>
                  )}
                </button>
              </div>

              <div className="rounded-lg bg-blue-50 p-4">
                <p className="text-sm text-blue-800">
                  💡 <strong>提示：</strong>
                  點擊「繼續新增課程」可以為同一預約加入更多課程（不同日期/時段）。
                  點擊「完成並加入購物車」將結束此次預約並加入購物車。
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Toast 通知 */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={hideToast}
        />
      )}
    </div>
  )
}

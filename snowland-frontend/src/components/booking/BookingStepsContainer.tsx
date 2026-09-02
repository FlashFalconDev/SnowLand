import { useState, useEffect } from 'react'
import { useBookingStore } from '@/store/bookingStore'
import { X, ChevronLeft, Home, ShoppingCart, UserCheck, Package, BookOpen, Calendar, Clock, ClipboardList, type LucideIcon } from 'lucide-react'
import CoachSelector from './steps/CoachSelector'
import EquipmentSelector from './steps/EquipmentSelector'
import CourseTemplateGrid from './steps/CourseTemplateGrid'
import CustomCalendar from './steps/CustomCalendar'
import TimeSlotSelector from './steps/TimeSlotSelector'
import Toast from '@/components/ui/Toast'
import { useToast } from '@/hooks/useToast'

interface BookingStepsContainerProps {
  onClose: () => void
  onComplete: () => void
}

type BookingStep = 1 | 2 | 3 | 4 | 5

const STEP_TITLES = {
  1: '選擇教練',
  2: '裝備租借',
  3: '選擇課程模板',
  4: '選擇日期',
  5: '選擇時段',
}

const STEP_ICONS: Record<BookingStep, LucideIcon> = {
  1: UserCheck,
  2: Package,
  3: BookOpen,
  4: Calendar,
  5: Clock,
}

const STEP_DESCRIPTIONS = {
  1: '請選擇您希望的教練，或選擇不指定教練由系統自動安排',
  2: '告訴我們您是否需要租借滑雪裝備',
  3: '選擇最適合您的課程時長和類型',
  4: '選擇您想要上課的日期',
  5: '選擇您想要的上課時段',
}

export default function BookingStepsContainer({
  onClose,
  onComplete,
}: BookingStepsContainerProps) {
  const [currentStep, setCurrentStep] = useState<BookingStep>(1)
  const { toast, hideToast, success, error, warning } = useToast()

  const startNewReservationGroup = useBookingStore((state) => state.startNewReservationGroup)
  const currentReservationGroup = useBookingStore((state) => state.currentReservationGroup)
  const finishCurrentGroupAndAddToCart = useBookingStore(
    (state) => state.finishCurrentGroupAndAddToCart
  )

  // 組件掛載時初始化預約組
  useEffect(() => {
    if (!currentReservationGroup) {
      startNewReservationGroup()
    }
  }, [])

  const handleNext = () => {
    if (currentStep < 5) {
      setCurrentStep((prev) => (prev + 1) as BookingStep)
    }
    // Step 5 的處理移到 TimeSlotSelector 中
  }

  const goToStep = (step: BookingStep) => {
    setCurrentStep(step)
  }

  const handleFinishAndAddToCart = () => {
    if (!currentReservationGroup || currentReservationGroup.courses.length === 0) {
      warning('請先完成至少一堂課程的選擇')
      return
    }

    finishCurrentGroupAndAddToCart()
    success(`已將 ${currentReservationGroup.courses.length} 堂課程加入購物車！`)
    onComplete()
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => (prev - 1) as BookingStep)
    }
  }

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return <CoachSelector onNext={handleNext} onBack={onClose} />
      case 2:
        return <EquipmentSelector onNext={handleNext} onBack={handleBack} />
      case 3:
        return <CourseTemplateGrid onNext={handleNext} onBack={handleBack} />
      case 4:
        return <CustomCalendar onNext={handleNext} onBack={handleBack} />
      case 5:
        return (
          <TimeSlotSelector
            onNext={handleNext}
            onBack={handleBack}
            onComplete={onComplete}
            goToStep={goToStep}
          />
        )
      default:
        return null
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* 當前預約組摘要 */}
      {currentReservationGroup && currentReservationGroup.courses.length > 0 && (
        <div className="mb-6 rounded-2xl bg-gradient-to-r from-blue-50 to-purple-50 p-6 shadow-md">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-bold text-gray-800">
            <ClipboardList size={20} className="text-primary-600" />
            <span>本次預約已選擇的課程 ({currentReservationGroup.courses.length} 堂)</span>
          </h3>
          <div className="space-y-2">
            {currentReservationGroup.courses.map((course, index) => (
              <div
                key={`${course.date}-${index}`}
                className="rounded-lg bg-white p-3 text-sm shadow-sm"
              >
                <span className="font-semibold text-primary-600">
                  課程 {index + 1}:
                </span>{' '}
                <span className="text-gray-700">
                  {course.date} • {course.timeSlotStart} - {course.timeSlotEnd} •{' '}
                  {course.courseTypeName}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 步驟導航卡片 */}
      <div className="mb-8 overflow-hidden rounded-2xl bg-white shadow-lg">
        {/* Header */}
        <div className="bg-gradient-to-r from-primary-500 to-purple-500 px-6 py-6 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={currentStep === 1 ? onClose : handleBack}
                className="flex items-center gap-2 rounded-full bg-white/20 px-4 py-2 transition-all hover:bg-white/30"
                title={currentStep === 1 ? '返回首頁' : '返回上一步'}
              >
                {currentStep === 1 ? (
                  <>
                    <Home size={20} />
                    <span className="hidden sm:inline">返回首頁</span>
                  </>
                ) : (
                  <>
                    <ChevronLeft size={20} />
                    <span className="hidden sm:inline">上一步</span>
                  </>
                )}
              </button>
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-white/20 p-2">
                  {(() => {
                    const StepIcon = STEP_ICONS[currentStep]
                    return <StepIcon size={32} />
                  })()}
                </div>
                <h2 className="text-2xl font-bold sm:text-3xl">
                  {STEP_TITLES[currentStep]}
                </h2>
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold">{currentStep}</div>
              <div className="text-sm text-white/80">/ 5</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-6 flex gap-2">
            {[1, 2, 3, 4, 5].map((step) => (
              <div
                key={step}
                className="relative flex-1"
              >
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    step <= currentStep ? 'bg-white' : 'bg-white/30'
                  }`}
                />
                <div
                  className={`mt-2 text-center text-xs transition-all ${
                    step <= currentStep ? 'text-white font-semibold' : 'text-white/60'
                  }`}
                >
                  {STEP_TITLES[step]}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="rounded-2xl bg-white p-8 shadow-lg">
        {renderStep()}
      </div>

      {/* 固定的「加入購物車」按鈕 - 只要有課程就顯示 */}
      {currentReservationGroup && currentReservationGroup.courses.length > 0 && (
        <div className="fixed bottom-8 right-8 z-40">
          <button
            onClick={handleFinishAndAddToCart}
            className="flex items-center gap-2 rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-6 py-4 text-lg font-bold text-white shadow-2xl transition-all hover:scale-105 hover:shadow-3xl"
          >
            <ShoppingCart size={24} />
            <span>完成並加入購物車 ({currentReservationGroup.courses.length})</span>
          </button>
        </div>
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
    </main>
  )
}

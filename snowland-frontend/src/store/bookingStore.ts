import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { BookingState, CartItem, EquipmentOption, Course, ReservationGroup } from '@/types/booking'

interface BookingStore extends BookingState {
  // 購物車
  cart: CartItem[]

  // 當前正在建立的預約組
  currentReservationGroup: ReservationGroup | null

  // 額外儲存名稱（用於購物車顯示）
  selectedCourseCategoryName: string | null
  selectedResortName: string | null

  // Actions - 前置選項
  setSelectedCourseCategory: (id: number, name: string) => void
  setSelectedResort: (resort: string | null, resortName: string | null) => void
  setSelectedCourseType: (id: number | null) => void
  setPeopleCount: (count: number) => void
  setHasUnder6: (has: boolean) => void
  setUnder7CanSelfSki: (can: boolean) => void
  setAbilityLevelCount: (level: string, count: number) => void
  setSelectedAbilityLevel: (level: string) => void
  setSelectedCoach: (id: number | null) => void
  setSelectedCourseTemplate: (id: number | null) => void
  setSelectedDate: (date: string | null) => void
  setSelectedTimeSlot: (id: number | null) => void
  setSelectedLanguage: (lang: string | null) => void
  setNeedEquipment: (need: boolean) => void
  setEquipmentOption: (option: EquipmentOption | null) => void
  setEquipmentAssistanceTimeSlot: (id: number | null, label?: string) => void
  setCurrentGroupFees: (fees: {
    courseFee?: number
    coachFee?: number
    languageFee?: number
    equipmentRentalFee?: number
  }) => void

  // 預約組操作
  startNewReservationGroup: () => void
  addCourseToCurrentGroup: (course: Course) => void
  finishCurrentGroupAndAddToCart: () => void

  // 購物車操作
  replaceCart: (cart: CartItem[]) => void
  removeFromCart: (id: string) => void
  removeCourseFromGroup: (groupId: string, courseIndex: number) => void
  clearCart: () => void

  // 重置
  resetStepSelection: () => void // 只重置步驟選擇，保留預約組
  resetAll: () => void // 完全重置
}

const initialState: BookingState = {
  selectedCourseCategory: null,
  selectedResort: null,
  selectedCourseType: null,
  peopleCount: 1,
  hasUnder6: false,
  under7CanSelfSki: false,
  abilityLevelCounts: {},
  selectedAbilityLevel: 'no_exp',
  selectedCoach: null,
  selectedCourseTemplate: null,
  selectedDate: null,
  selectedTimeSlot: null,
  selectedLanguage: null,
  needEquipment: false,
  equipmentOption: null,
  equipmentAssistanceTimeSlotId: null,
  equipmentAssistanceTimeLabel: '',
}

// 額外的初始狀態（不在 BookingState type 中）
const extendedInitialState = {
  ...initialState,
  selectedCourseCategoryName: null as string | null,
  selectedResortName: null as string | null,
}

export const useBookingStore = create<BookingStore>()(
  persist(
    (set, get) => ({
      ...extendedInitialState,
      cart: [],
      currentReservationGroup: null,

      // 前置選項設定
      setSelectedCourseCategory: (id, name) => set({ selectedCourseCategory: id, selectedCourseCategoryName: name }),
      setSelectedResort: (resort, resortName) => set({ selectedResort: resort, selectedResortName: resortName }),
  setSelectedCourseType: (id) => set({ selectedCourseType: id }),
  setPeopleCount: (count) => set({ peopleCount: count, abilityLevelCounts: {}, selectedAbilityLevel: 'no_exp' }),
  setHasUnder6: (has) => set((state) => ({
    hasUnder6: has,
    under7CanSelfSki: has ? state.under7CanSelfSki : false,
  })),
  setUnder7CanSelfSki: (can) => set({ under7CanSelfSki: can }),
  setAbilityLevelCount: (level, count) => set((state) => {
    const normalizedCount = Math.max(0, Number(count) || 0)
    const nextCounts = { ...(state.abilityLevelCounts || {}) }
    if (normalizedCount > 0) nextCounts[level] = normalizedCount
    else delete nextCounts[level]

    return {
      abilityLevelCounts: nextCounts,
      selectedAbilityLevel: getHighestBackendAbilityLevel(nextCounts),
    }
  }),
  setSelectedAbilityLevel: (level) => set({ selectedAbilityLevel: level }),
  setSelectedCoach: (id) => set({ selectedCoach: id }),
  setSelectedCourseTemplate: (id) => set({ selectedCourseTemplate: id }),
  setSelectedDate: (date) => set({ selectedDate: date }),
  setSelectedTimeSlot: (id) => set({ selectedTimeSlot: id }),
  setSelectedLanguage: (lang) => set({ selectedLanguage: lang }),
  setNeedEquipment: (need) => set({ needEquipment: need }),
  setEquipmentOption: (option) => set({ equipmentOption: option }),
  setEquipmentAssistanceTimeSlot: (id, label = '') => set({
    equipmentAssistanceTimeSlotId: id,
    equipmentAssistanceTimeLabel: id ? label : '',
  }),

      // 開始新的預約組（當前置選項完成時調用）
      startNewReservationGroup: () => {
        const state = get()
        const newGroup: ReservationGroup = {
          id: `group-${Date.now()}`,
          coach: state.selectedCoach || 'any',
          coachName: state.selectedCoach ? `教練 #${state.selectedCoach}` : '不指定',
          peopleCount: state.peopleCount,
          abilityLevel: state.selectedAbilityLevel,
          abilityLevelName: getAbilityLevelSummary(state.abilityLevelCounts) || getAbilityLevelName(state.selectedAbilityLevel),
          abilityLevelCounts: state.abilityLevelCounts,
          equipment: state.needEquipment,
          equipmentOption: state.equipmentOption,
          equipmentAssistanceTimeSlotId: state.equipmentAssistanceTimeSlotId,
          equipmentAssistanceTimeLabel: state.equipmentAssistanceTimeLabel,
          language: state.selectedLanguage,
          resort: state.selectedResort || '',
          resortName: state.selectedResortName || state.selectedResort || '',
          courseCategory: state.selectedCourseCategoryName || '未指定', // 使用儲存的名稱
          courseFee: 0,
          coachFee: 0,
          languageFee: 0,
          equipmentRentalFee: 0,
          courses: [],
          totalPrice: null,
        }
        set({ currentReservationGroup: newGroup })
      },

  // 將課程加入當前預約組
  addCourseToCurrentGroup: (course) => {
    set((state) => {
      if (!state.currentReservationGroup) return state

      const updatedGroup = {
        ...state.currentReservationGroup,
        courses: [...state.currentReservationGroup.courses, course],
      }
      updatedGroup.totalPrice = calculateReservationGroupTotal(updatedGroup)

      return { currentReservationGroup: updatedGroup }
    })
  },

  // 完成當前預約組並加入購物車
  setCurrentGroupFees: (fees) => {
    set((state) => {
      if (!state.currentReservationGroup) return state
      const updatedGroup = {
        ...state.currentReservationGroup,
        courseFee: fees.courseFee ?? state.currentReservationGroup.courseFee ?? 0,
        coachFee: fees.coachFee ?? state.currentReservationGroup.coachFee ?? 0,
        languageFee: fees.languageFee ?? state.currentReservationGroup.languageFee ?? 0,
        equipmentRentalFee: fees.equipmentRentalFee ?? state.currentReservationGroup.equipmentRentalFee ?? 0,
      }
      updatedGroup.totalPrice = calculateReservationGroupTotal(updatedGroup)
      return { currentReservationGroup: updatedGroup }
    })
  },

  finishCurrentGroupAndAddToCart: () => {
    set((state) => {
      if (!state.currentReservationGroup || state.currentReservationGroup.courses.length === 0) {
        return state
      }

      return {
        cart: [...state.cart, state.currentReservationGroup],
        currentReservationGroup: null,
      }
    })
  },

  // 從購物車移除整個預約組
  replaceCart: (cart) => set({ cart }),

  removeFromCart: (id) =>
    set((state) => ({
      cart: state.cart.filter((item) => item.id !== id),
    })),

  // 從預約組中移除單堂課程
  removeCourseFromGroup: (groupId, courseIndex) =>
    set((state) => {
      const updatedCart = state.cart.map((group) => {
        if (group.id === groupId) {
          const originalCourseCount = group.courses.length
          const updatedCourses = group.courses.filter((_, index) => index !== courseIndex)
          // 如果課程全部被刪除，則移除整個預約組
          if (updatedCourses.length === 0) {
            return null
          }
          const updatedGroup = {
            ...group,
            courses: updatedCourses,
            courseFee: calculateGroupTotalPrice(updatedCourses) ?? 0,
            coachFee: scalePerCourseFee(group.coachFee, originalCourseCount, updatedCourses.length),
            languageFee: scalePerCourseFee(group.languageFee, originalCourseCount, updatedCourses.length),
            equipmentRentalFee: scalePerCourseFee(group.equipmentRentalFee, originalCourseCount, updatedCourses.length),
          }
          updatedGroup.totalPrice = calculateReservationGroupTotal(updatedGroup)
          return updatedGroup
        }
        return group
      }).filter((group): group is ReservationGroup => group !== null)

      return { cart: updatedCart }
    }),

  clearCart: () => set({ cart: [], currentReservationGroup: null }),

  // 只重置步驟選擇（用於繼續新增課程）
  resetStepSelection: () =>
    set({
      selectedCourseTemplate: null,
      selectedDate: null,
      selectedTimeSlot: null,
    }),

      // 完全重置
      resetAll: () => set({ ...extendedInitialState, cart: [], currentReservationGroup: null }),
    }),
    {
      name: 'booking-storage', // localStorage key
      partialize: (state) => ({
        cart: state.cart, // 只持久化購物車
      }),
    }
  )
)

// 輔助函數：獲取能力等級名稱
function getAbilityLevelName(level: string): string {
  const levelMap: Record<string, string> = {
    no_exp: '等級 0',
    level1: '等級 1',
    level2: '等級 2',
    level3: '等級 3',
    level4: '等級 4',
    level5: '等級 5',
    level6: '等級 6',
    entry: '等級 1',
    basic: '等級 2',
    intermediate: '等級 3',
    advanced: '等級 4',
    expert: '等級 6',
    some_exp: '有經驗',
    can_turn: '可轉彎',
  }
  return levelMap[level] || level
}

const abilityLevelOrder = ['no_exp', 'level1', 'level2', 'level3', 'level4', 'level5', 'level6']

const abilityBackendMap: Record<string, string> = {
  no_exp: 'no_exp',
  level1: 'level1',
  level2: 'level2',
  level3: 'level3',
  level4: 'level4',
  level5: 'level5',
  level6: 'level6',
}

function getHighestBackendAbilityLevel(counts: Record<string, number>): string {
  const highest = [...abilityLevelOrder].reverse().find((level) => (counts[level] || 0) > 0)
  return highest ? abilityBackendMap[highest] : 'no_exp'
}

function getAbilityLevelSummary(counts: Record<string, number>): string {
  return abilityLevelOrder
    .filter((level) => (counts[level] || 0) > 0)
    .map((level) => `${getAbilityLevelName(level)} ${counts[level]} 人`)
    .join('、')
}

// 輔助函數：計算預約組總價
function calculateGroupTotalPrice(courses: Course[]): number | null {
  if (courses.some((c) => c.price === null)) {
    return null // 有課程價格未計算
  }
  return courses.reduce((sum, course) => sum + (course.price || 0), 0)
}

function calculateReservationGroupTotal(group: ReservationGroup): number | null {
  const courseTotal = calculateGroupTotalPrice(group.courses)
  if (courseTotal === null) return null
  return (
    courseTotal +
    (group.coachFee || 0) +
    (group.languageFee || 0) +
    (group.equipmentRentalFee || 0)
  )
}

function scalePerCourseFee(value: number | null | undefined, originalCount: number, nextCount: number): number {
  if (!value || originalCount <= 0) return 0
  return Math.round((value * nextCount) / originalCount)
}

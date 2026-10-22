import type { CartItem } from '@/types/booking'

export const hasUnconfirmedCartPrice = (cart: CartItem[]) => cart.some(group =>
  group.totalPrice == null || !Number.isFinite(group.totalPrice)
  || !group.courses?.length || group.courses.some(course => course.price == null || !Number.isFinite(course.price)),
)

export const isPhotoCartGroup = (group: CartItem) => {
  if (group.serviceType === 'photo' || group.serviceType === 'ski') return group.serviceType === 'photo'
  // Compatibility for carts saved before serviceType was persisted.
  return /攝影|旅拍|photography|photo/i.test([
    group.courseCategory,
    ...(group.courses || []).map(course => `${course.courseTypeName} ${course.courseTemplateName}`),
  ].join(' '))
}

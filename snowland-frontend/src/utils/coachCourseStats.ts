import type { MyCourse } from '../admin/api/extras'

type StatsCourse = Pick<MyCourse, 'shared_class_id' | 'course_category' | 'course_type' | 'is_preferred_coach' | 'bookings'>

function timeMinutes(value: string) {
  const [hour, minute] = value.split(':').map(Number)
  return Number.isFinite(hour) && Number.isFinite(minute) ? hour * 60 + minute : 0
}

export function calculateCoachCourseStats(items: StatsCourse[], month: string) {
  const stats = { totalHours: 0, snowboardHours: 0, skiHours: 0, specifiedHours: 0, lessons: 0 }
  const countedLessons = new Set<string>()
  for (const item of items) {
    for (const booking of item.bookings) {
      if (!booking.date?.startsWith(month)) continue
      // Shared-class orders are separate payments, not separate teaching hours.
      const key = item.shared_class_id
        ? `class:${item.shared_class_id}:${booking.date}:${booking.start_time}:${booking.end_time}`
        : `booking:${booking.id}`
      if (countedLessons.has(key)) continue
      countedLessons.add(key)
      const hours = Math.max((timeMinutes(booking.end_time) - timeMinutes(booking.start_time)) / 60, 0)
      stats.totalHours += hours
      stats.lessons += 1
      if (item.is_preferred_coach) stats.specifiedHours += hours
      const kind = `${item.course_category || ''} ${item.course_type || ''}`.toLowerCase()
      if (kind.includes('snowboard') || kind.includes('單板')) stats.snowboardHours += hours
      else if (kind.includes('ski') || kind.includes('雙板')) stats.skiHours += hours
    }
  }
  return stats
}

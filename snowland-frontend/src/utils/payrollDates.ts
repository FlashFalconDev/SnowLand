export function payrollMonthRange(now = new Date()) {
  const year = now.getFullYear()
  const month = now.getMonth()
  const prefix = `${year}-${String(month + 1).padStart(2, '0')}`
  // Date fields are local calendar days; converting midnight to UTC can subtract a day.
  return { first: `${prefix}-01`, last: `${prefix}-${String(new Date(year, month + 1, 0).getDate()).padStart(2, '0')}` }
}

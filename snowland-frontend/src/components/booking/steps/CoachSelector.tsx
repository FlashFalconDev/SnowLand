import { useState, useEffect } from 'react'
import { useBookingStore } from '@/store/bookingStore'
import { fetchCoaches } from '@/api/booking'
import { Search, UserCheck, Globe } from 'lucide-react'

interface CoachSelectorProps {
  onNext: () => void
  onBack: () => void
}

interface Coach {
  id: number
  name: string
  languages: string[]
  price_level: string
  avatar?: string
}

const LANGUAGE_OPTIONS = [
  { value: 'all', label: '全部語言' },
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
  { value: 'yue', label: '廣東話' },
]

export default function CoachSelector({ onNext, onBack }: CoachSelectorProps) {
  const [coaches, setCoaches] = useState<Coach[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState('all')

  const selectedResort = useBookingStore((state) => state.selectedResort)
  const selectedCourseType = useBookingStore((state) => state.selectedCourseType)
  const selectedAbilityLevel = useBookingStore((state) => state.selectedAbilityLevel)
  const setSelectedCoach = useBookingStore((state) => state.setSelectedCoach)

  useEffect(() => {
    const loadCoaches = async () => {
      if (!selectedResort || !selectedCourseType) return

      try {
        setLoading(true)
        setError(null)
        const data = await fetchCoaches({
          resort: selectedResort,
          courseType: selectedCourseType.toString(),
          abilityLevel: selectedAbilityLevel,
        })
        // API 返回格式：{ coach_list: [...], courses: [] }
        setCoaches(data.coach_list || [])
      } catch (err) {
        console.error('載入教練列表失敗:', err)
        setError('載入教練列表失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    loadCoaches()
  }, [selectedResort, selectedCourseType, selectedAbilityLevel])

  const filteredCoaches = coaches.filter((coach) => {
    const matchesSearch = coach.name
      .toLowerCase()
      .includes(searchTerm.toLowerCase())
    const matchesLanguage =
      selectedLanguage === 'all' || coach.languages.includes(selectedLanguage)
    return matchesSearch && matchesLanguage
  })

  const handleSelectCoach = (coachId: number | null, coachName?: string) => {
    setSelectedCoach(coachId, coachName)
    onNext()
  }

  return (
    <div className="space-y-6">
      {/* 搜尋和篩選 */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* 搜尋框 */}
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            size={20}
          />
          <input
            type="text"
            placeholder="搜尋教練名稱..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
          />
        </div>

        {/* 語言篩選 */}
        <div className="relative">
          <Globe
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            size={20}
          />
          <select
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            className="w-full appearance-none rounded-lg border border-gray-300 py-2 pl-10 pr-4 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 不指定教練選項 */}
      <button
        onClick={() => handleSelectCoach(null)}
        className="w-full rounded-xl border-2 border-dashed border-primary-300 bg-primary-50 p-6 text-left transition-all hover:border-primary-500 hover:bg-primary-100"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-200 text-3xl">
            🎲
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-primary-700">
              不指定教練
            </h3>
            <p className="mt-1 text-sm text-primary-600">
              系統將為您自動安排合適的教練
            </p>
          </div>
          <UserCheck size={24} className="text-primary-500" />
        </div>
      </button>

      {/* Loading */}
      {loading && (
        <div className="py-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">載入教練列表中...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-600">{error}</div>
      )}

      {/* 教練列表 */}
      {!loading && !error && (
        <div className="space-y-3">
          {filteredCoaches.length === 0 ? (
            <div className="rounded-lg bg-yellow-50 p-6 text-center">
              <p className="text-yellow-800">
                😔 沒有找到符合條件的教練
              </p>
              <p className="mt-2 text-sm text-yellow-700">
                請調整篩選條件或選擇「不指定教練」
              </p>
            </div>
          ) : (
            filteredCoaches.map((coach) => (
              <button
                key={coach.id}
                onClick={() => handleSelectCoach(coach.id, coach.name)}
                className="w-full rounded-xl border-2 border-gray-200 bg-white p-4 text-left transition-all hover:border-primary-500 hover:shadow-lg"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-primary-100 to-purple-100 text-2xl font-bold text-primary-700">
                    {coach.name.charAt(0)}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-gray-800">
                      {coach.name}
                    </h3>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {coach.languages.map((lang) => (
                        <span
                          key={lang}
                          className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700"
                        >
                          {
                            LANGUAGE_OPTIONS.find((opt) => opt.value === lang)
                              ?.label || lang
                          }
                        </span>
                      ))}
                      <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                        {coach.price_level === 'director'
                          ? '校長/總監'
                          : coach.price_level === 'Lv2'
                          ? '二級教練'
                          : '一般教練'}
                      </span>
                    </div>
                  </div>
                  <UserCheck size={20} className="text-gray-300" />
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

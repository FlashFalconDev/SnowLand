import { useNavigate } from 'react-router-dom'
import { Mountain, Sparkles, Users, Calendar, ArrowRight } from 'lucide-react'

export default function ClientSelectionPage() {
  const navigate = useNavigate()

  const clients = [
    {
      code: 'snowland',
      name: '雪域滑雪',
      description: '專業滑雪課程預約平台',
      color: 'from-purple-500 to-pink-600',
      icon: Mountain,
    },
    // 未來可以在這裡添加更多客戶
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-pink-900">
      {/* 背景裝飾 */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-fuchsia-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Header */}
        <header className="pt-12 pb-8 px-4">
          <div className="max-w-6xl mx-auto text-center">
            <div className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-br from-purple-400 to-pink-500 rounded-full mb-6 shadow-2xl">
              <Mountain className="w-12 h-12 text-white" />
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-white mb-4 tracking-tight">
              滑雪課程預約系統
            </h1>
            <p className="text-xl text-purple-100 max-w-2xl mx-auto">
              專業的滑雪教練配對與課程管理平台
            </p>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 px-4 pb-16">
          <div className="max-w-6xl mx-auto">
            {/* 客戶卡片區域 */}
            <div className="mb-16">
              <h2 className="text-2xl font-bold text-white text-center mb-8">選擇您的滑雪場</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {clients.map((client) => (
                  <button
                    key={client.code}
                    onClick={() => {
                      localStorage.setItem('client_code', client.code)
                      navigate(`/${client.code}`)
                    }}
                    className="group relative bg-white/10 backdrop-blur-md rounded-3xl p-8 hover:bg-white/20 transition-all duration-300 hover:scale-105 hover:shadow-2xl border border-white/20"
                  >
                    <div className={`inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br ${client.color} rounded-2xl mb-4 shadow-lg group-hover:scale-110 transition-transform`}>
                      <client.icon className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-2">{client.name}</h3>
                    <p className="text-purple-100 mb-4">{client.description}</p>
                    <div className="flex items-center text-purple-200 font-medium">
                      <span>開始預約</span>
                      <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* 功能特色 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-purple-400 to-purple-600 rounded-xl mb-4">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">AI 智能排課</h3>
                <p className="text-purple-100 text-sm">
                  根據您的需求自動匹配最合適的教練和時段
                </p>
              </div>

              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-pink-400 to-pink-600 rounded-xl mb-4">
                  <Users className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">專業教練團隊</h3>
                <p className="text-purple-100 text-sm">
                  經驗豐富的滑雪教練，提供優質的教學服務
                </p>
              </div>

              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-fuchsia-400 to-fuchsia-600 rounded-xl mb-4">
                  <Calendar className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">彈性選擇</h3>
                <p className="text-purple-100 text-sm">
                  多種課程時段和類型，靈活安排您的滑雪行程
                </p>
              </div>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="py-8 px-4 border-t border-white/10">
          <div className="max-w-6xl mx-auto text-center">
            <p className="text-purple-200 text-sm">
              © 2024 滑雪課程預約系統. All rights reserved.
            </p>
          </div>
        </footer>
      </div>

      {/* CSS 動畫 */}
      <style>{`
        @keyframes blob {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
          100% { transform: translate(0px, 0px) scale(1); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  )
}

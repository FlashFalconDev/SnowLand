import React from 'react';
import { motion } from 'framer-motion';
import SiteFooter from '../../components/site/SiteFooter';
import SiteHeader from '../../components/site/SiteHeader';
import SiteLink from '../../components/site/SiteLink';
import { useSiteLocale } from '../../contexts/SiteLocale';

const steps = [
  {
    num: '01',
    title: '選擇課程',
    desc: '登入會員後，選擇課程大類、雪場及人數，再分配每位學員的滑雪程度。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11H3v10h6V11zM15 3H9v18h6V3zM21 7h-6v14h6V7z" />
      </svg>
    ),
  },
  {
    num: '02',
    title: '選擇日期時段',
    desc: '依畫面選擇課程方案、開放日期及時段；時長、最低人數與可預約範圍以所選課程為準。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    num: '03',
    title: '教練與裝備',
    desc: '依課程提供的選項設定教練、語言與裝備需求，再將課程加入購物車。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    num: '04',
    title: '確認聯絡資料',
    desc: '確認購物車的日期、人數及價格，填寫聯絡資料與活動來源，閱讀並確認訂單條款後送出。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4" />
        <path d="M4 6v12c0 1.1.9 2 2 2h14v-4" />
        <path d="M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4h-4z" />
      </svg>
    ),
  },
  {
    num: '05',
    title: '確認安排與付款',
    desc: '若訂單等待教練確認、課服安排或團體成班，請先勿付款。開放付款後，依訂單顯示的方式與期限完成付款。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
        <line x1="1" y1="10" x2="23" y2="10" />
      </svg>
    ),
  },
  {
    num: '06',
    title: '查看訂單與課前資料',
    desc: '到會員訂單查看最新安排及付款狀態，並逐位完成學員資料、保險資料及課前聲明；資料填妥不代表已完成投保。',
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    ),
  },
];

const notes = [
  {
    title: '取消與更改規定',
    desc: '請先查看取消與更改規定；會員訂單的取消試算為預估值，實際退款仍須核對實收款及行政審核。',
    href: '/cancellation-policy',
  },
  {
    title: '付款方式',
    desc: '依訂單顯示的幣別、付款方式與收款帳戶付款；未開放付款前請勿匯款。',
  },
  {
    title: '優惠與折扣',
    desc: '優惠依當期設定及適用條件計算；請以結帳時顯示的折扣與應付金額為準。',
  },
  {
    title: '裝備準備',
    desc: '依所選課程與雪場提供的選項選擇裝備需求；加購服務、集合時間及費用請以訂單資訊為準。',
  },
];

function CourseHowToBookPage() {
  const { t } = useSiteLocale();
  return (
    <div className="min-h-screen bg-white text-[#1f2937] flex flex-col">
      <SiteHeader forceTransparent forceDarkText forceLogoColor />

      <main className="flex-1 w-full pt-28 md:pt-32">
        {/* Hero */}
        <section className="max-w-5xl mx-auto px-6 md:px-10 py-10 md:py-16 text-center">
          <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
            Ski Course
          </p>
          <h1 className="mt-4 text-3xl md:text-4xl font-semibold tracking-wide font-display">
            {t('預約流程')}
          </h1>
          <p className="mt-6 text-sm md:text-base text-[#6b7280] leading-relaxed max-w-2xl mx-auto">
            {t('六個簡單步驟，為您安排最適合的滑雪課程。')}<br />
            {t('如有任何疑問，歡迎透過 Line、WhatsApp 或聯絡表單與我們聯繫。')}
          </p>
        </section>

        {/* Steps Timeline */}
        <section className="bg-[#f7f8fa] py-16 md:py-24">
          <div className="max-w-5xl mx-auto px-6 md:px-10">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
              {steps.map((step, index) => (
                <motion.article
                  key={step.num}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.5, delay: index * 0.08, ease: 'easeOut' }}
                  className="group relative bg-white border border-[#e5e9f2] rounded-sm p-8 md:p-10 shadow-[0_10px_24px_rgba(15,23,42,0.04)] hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)] transition-shadow"
                >
                  <div className="flex items-start gap-5">
                    <div className="shrink-0 flex h-12 w-12 items-center justify-center rounded-full bg-[#e9eef3] text-[#2b5f8f] group-hover:bg-[#2b5f8f] group-hover:text-white transition-colors">
                      {step.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-2xl font-bold text-[#2b5f8f] font-display leading-none">
                        {step.num}
                      </p>
                      <h3 className="mt-3 text-lg md:text-xl font-semibold text-[#1f2937] font-display">
                        {t(step.title)}
                      </h3>
                      <p className="mt-3 text-sm text-[#6b7280] leading-relaxed">
                        {t(step.desc)}
                      </p>
                    </div>
                  </div>
                </motion.article>
              ))}
            </div>

            {/* CTA */}
            <div className="mt-16 md:mt-20 text-center">
              <SiteLink
                to="/booking"
                className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-10 py-4 text-base font-semibold text-white hover:bg-[#8ec8f0] transition-colors shadow-lg hover:shadow-xl"
              >
                {t('立即預約課程')}
                <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </SiteLink>
            </div>
          </div>
        </section>

        {/* Notes / FAQ 簡要 */}
        <section className="bg-white py-16 md:py-24">
          <div className="max-w-5xl mx-auto px-6 md:px-10">
            <div className="text-center mb-12 md:mb-16">
              <p className="text-xs md:text-sm tracking-[0.3em] uppercase text-[#6b7280] font-medium font-display">
                Notes
              </p>
              <h2 className="text-2xl font-semibold text-[#1f2937] mt-4 font-display">
                {t('注意事項')}
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
              {notes.map((note) => (
                <div
                  key={note.title}
                  className="border-l-2 border-[#2b5f8f] pl-6 py-2"
                >
                  <h3 className="text-base font-semibold text-[#1f2937] font-display">
                    {t(note.title)}
                  </h3>
                  <p className="mt-3 text-sm text-[#6b7280] leading-relaxed">
                    {t(note.desc)}
                  </p>
                  {note.href && <SiteLink to={note.href} className="mt-2 inline-flex min-h-11 items-center text-sm font-semibold text-[#2b5f8f] underline underline-offset-4">{t('查看取消與更改規定')}</SiteLink>}
                </div>
              ))}
            </div>

            <div className="mt-12 md:mt-16 text-center text-sm text-[#6b7280]">
              {t('更多問題請參考')}{' '}
              <SiteLink to="/faq" className="text-[#2b5f8f] font-semibold underline underline-offset-4 hover:text-[#8ec8f0]">
                {t('常見問題')}
              </SiteLink>
              {' '}{t('或')}{' '}
              <SiteLink to="/contact" className="text-[#2b5f8f] font-semibold underline underline-offset-4 hover:text-[#8ec8f0]">
                {t('聯絡我們')}
              </SiteLink>
              。
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

export default CourseHowToBookPage;

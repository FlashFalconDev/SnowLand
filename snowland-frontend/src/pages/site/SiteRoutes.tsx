import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import ScrollToTop from '@/components/site/ScrollToTop'

// HomePage is loaded eagerly — it's the first thing users see
import HomePage from './HomePage'

// Everything else is lazy loaded and cached by the browser
const CoachPage = lazy(() => import('./CoachPage'))
const CoachTeamPage = lazy(() => import('./CoachTeamPage'))
const ContactPage = lazy(() => import('./ContactPage'))
// BookingPage removed — /booking now routes to the real booking system in App.tsx
const MembershipPage = lazy(() => import('./MembershipPage'))
const FaqPage = lazy(() => import('./FaqPage'))
const PolicyPage = lazy(() => import('./PolicyPage'))
const NewsPage = lazy(() => import('./NewsPage'))
const TomamuCoursePage = lazy(() => import('./TomamuCoursePage'))
const HokkaidoCoursePage = lazy(() => import('./HokkaidoCoursePage'))
const ResortCoursePage = lazy(() => import('./ResortCoursePage'))
const OffPisteGuidePage = lazy(() => import('./OffPisteGuidePage'))
const CourseHowToBookPage = lazy(() => import('./CourseHowToBookPage'))
const SkiResortsPage = lazy(() => import('./SkiResortsPage'))
const GuidesCollectionPage = lazy(() => import('./GuidesCollectionPage'))
const BestHokkaidoTreeRunsPage = lazy(() => import('./BestHokkaidoTreeRunsPage'))
const PackingChecklistPage = lazy(() => import('./PackingChecklistPage'))
const LegacyContentPage = lazy(() => import('./LegacyContentPage'))
const OverseasPhotographyWorksPage = lazy(() => import('./OverseasPhotographyWorksPage'))
const WinterPhotographyPage = lazy(() => import('./WinterPhotographyPage'))
const SummerPhotographyPage = lazy(() => import('./SummerPhotographyPage'))

// Preload high-priority pages after HomePage renders
function usePreloadPages() {
  useEffect(() => {
    // Wait until the browser is idle, then start preloading popular pages
    const preload = () => {
      import('./CoachTeamPage')
      import('./TomamuCoursePage')
      import('./BookingPage')
      import('./FaqPage')
      import('./CoachPage')
      import('./HokkaidoCoursePage')
      import('./ContactPage')
    }

    if ('requestIdleCallback' in window) {
      ;(window as any).requestIdleCallback(preload)
    } else {
      setTimeout(preload, 2000)
    }
  }, [])
}

// Loading spinner shown while lazy pages load
function PageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="relative w-12 h-12 mx-auto mb-4">
          <div className="absolute inset-0 rounded-full border-2 border-[#e5e9f2]" />
          <div className="absolute inset-0 rounded-full border-2 border-t-[#2b5f8f] animate-spin" />
        </div>
        <p className="text-sm text-[#6b7280] font-display tracking-wide">
          載入中...
        </p>
      </div>
    </div>
  )
}

function SapporoRedirect() {
  const { section } = useParams()
  const target = section
    ? `/course/sapporo-kokusai/${section}`
    : '/course/sapporo-kokusai'
  return <Navigate to={target} replace />
}

export default function SiteRoutes() {
  // Start preloading other pages once HomePage is shown
  usePreloadPages()

  return (
    <>
      <ScrollToTop />
      <Suspense fallback={<PageLoading />}>
        <Routes>
          {/* Home — loaded eagerly, shows instantly */}
          <Route path="/" element={<HomePage />} />

          {/* Coach */}
          <Route path="/coach" element={<CoachTeamPage />} />
          <Route path="/coach/:slug" element={<CoachPage />} />

          {/* Courses */}
          <Route path="/course/tomamu" element={<TomamuCoursePage />} />
          <Route path="/course/tomamu/:section" element={<TomamuCoursePage />} />
          <Route path="/course/sapporo" element={<SapporoRedirect />} />
          <Route path="/course/sapporo/:section" element={<SapporoRedirect />} />
          <Route path="/course/off-piste-guide" element={<OffPisteGuidePage />} />
          <Route path="/course/hokkaido" element={<HokkaidoCoursePage />} />
          <Route path="/course/:resort" element={<ResortCoursePage />} />
          <Route path="/course/:resort/:section" element={<ResortCoursePage />} />
          <Route path="/course/how-to-book" element={<CourseHowToBookPage />} />

          {/* Photography */}
          <Route path="/Gallery" element={<OverseasPhotographyWorksPage />} />
          <Route path="/photography/winter" element={<WinterPhotographyPage />} />
          <Route path="/photography/summer" element={<SummerPhotographyPage />} />
          <Route path="/photography/how-to-book" element={<LegacyContentPage key="photography-how-to-book" pageKey="photography-how-to-book" />} />

          {/* Guides */}
          <Route path="/guides/skiresorts" element={<SkiResortsPage initialActiveSlug={undefined} />} />
          <Route path="/guides/preparation" element={<LegacyContentPage key="guides-preparation" pageKey="guides-preparation" />} />
          <Route path="/guides/faq" element={<LegacyContentPage key="guides-faq" pageKey="guides-faq" />} />
          <Route path="/guides" element={<GuidesCollectionPage />} />
          <Route path="/guides/:category" element={<GuidesCollectionPage />} />
          <Route path="/guides/best-hokkaido-tree-runs" element={<BestHokkaidoTreeRunsPage />} />
          <Route path="/guides/packing-checklist" element={<PackingChecklistPage />} />

          {/* Special Offers */}
          <Route path="/specialoffers" element={<LegacyContentPage key="deals" pageKey="deals" />} />
          <Route path="/specialoffers/earlybird" element={<LegacyContentPage key="deals-earlybird" pageKey="deals-earlybird" />} />
          <Route path="/specialoffers/referral" element={<LegacyContentPage key="deals-referral" pageKey="deals-referral" />} />
          <Route path="/specialoffers/promo" element={<LegacyContentPage key="deals-promo" pageKey="deals-promo" />} />

          {/* About & Info */}
          <Route path="/about" element={<LegacyContentPage key="about" pageKey="about" />} />
          <Route path="/join-us" element={<LegacyContentPage key="join-us" pageKey="join-us" />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/membership" element={<MembershipPage />} />
          <Route path="/membership/*" element={<MembershipPage />} />
          {/* /booking is handled by ClientRoutes → MainApp (real booking system) */}
          <Route path="/news" element={<NewsPage />} />

          {/* FAQ */}
          <Route path="/faq" element={<FaqPage />} />
          <Route path="/faq/:category" element={<FaqPage />} />

          {/* Policies */}
          <Route path="/membership-terms" element={<PolicyPage contentKey="membershipTerms" eyebrow="TERMS" />} />
          <Route path="/privacy-policy" element={<PolicyPage contentKey="privacyPolicy" eyebrow="PRIVACY" />} />
          <Route path="/cancellation-policy" element={<PolicyPage contentKey="cancellationPolicy" eyebrow="CANCELLATION" />} />

          {/* Fallback */}
          <Route path="*" element={<HomePage />} />
        </Routes>
      </Suspense>
    </>
  )
}

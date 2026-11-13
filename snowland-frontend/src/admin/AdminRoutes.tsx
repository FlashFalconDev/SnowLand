import { Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layout/AdminLayout'
import RoleGuard from './components/RoleGuard'
import DashboardPage from './pages/DashboardPage'
import ContactInboxPage from './pages/ContactInboxPage'
import RecruitmentPage from './pages/cms/RecruitmentPage'
import SocialSyncPage from './pages/SocialSyncPage'
import CoachesPage from './pages/CoachesPage'
import ResortsPage from './pages/ResortsPage'
import CampusesPage from './pages/CampusesPage'
import CourseTypesPage from './pages/CourseTypesPage'
import PricingPage from './pages/PricingPage'
import DiscountsPage from './pages/DiscountsPage'
import OrdersPage from './pages/OrdersPage'
import CustomersPage from './pages/CustomersPage'
import SchedulingPage from './pages/SchedulingPage'
import VehiclePage from './pages/VehiclePage'
import CoachWorkloadPanel from './components/CoachWorkloadPanel'
import CoachLeavesPage from './pages/CoachLeavesPage'
import StaffPermissionsPage from './pages/StaffPermissionsPage'
import PaymentSettingsPage from './pages/PaymentSettingsPage'
import ChatSupportPage from './pages/ChatSupportPage'
import CoachEditorPage from './pages/cms/CoachEditorPage'
import SiteContentPage from './pages/cms/SiteContentPage'
import PendingConfirmationsPage from './pages/my/PendingConfirmationsPage'
import MyCoursesPage from './pages/my/MyCoursesPage'
import MyCalendarPage from './pages/my/MyCalendarPage'
import MyLeavesPage from './pages/my/MyLeavesPage'
import ApplyLeavePage from './pages/my/ApplyLeavePage'
import MyPayrollPage from './pages/my/MyPayrollPage'
import OperationsHubPage from './pages/OperationsHubPage'
import FrontendSupportPage from './pages/FrontendSupportPage'

import type { ReactElement } from 'react'
import type { SiteContentType } from './api/siteContent'
import { consoleNavigation, type ConsolePath } from './consoleNavigation'

const REVIEW_TYPES: SiteContentType[] = ['review']
const MEDIA_TYPES: SiteContentType[] = ['media']
const pages: Record<ConsolePath, ReactElement> = {
  '': <DashboardPage />,
  'orders': <OrdersPage />,
  'orders/edit': <OrdersPage key="edit" mode="edit" />,
  'orders/payments': <OrdersPage key="payments" mode="payments" />,
  'orders/refunds': <OrdersPage key="refunds" mode="refunds" />,
  'booking-links': <OperationsHubPage initialTab="links" fixed />,
  'orders/export': <OrdersPage mode="export" />,
  'contact-inbox': <ContactInboxPage />,
  'chat-support': <ChatSupportPage />,
  'notifications': <OperationsHubPage initialTab="notifications" fixed />,
  'customers': <CustomersPage />,
  'insurance': <OperationsHubPage initialTab="insurance" fixed />,
  'customers/loyalty': <CustomersPage key="loyalty" loyalty />,
  'cms/membership': <SiteContentPage initialGroup="membership" section="course_documents" />,
  'scheduling': <SchedulingPage />,
  'vehicles/review': <VehiclePage key="vehicle-review" mode="review" />,
  'vehicles/finance': <VehiclePage key="vehicle-finance" mode="finance" />,
  'my/vehicles': <VehiclePage key="vehicle-coach" mode="coach" />,
  'coach-workload': <CoachWorkloadPanel />,
  'coaches': <CoachesPage />,
  'coaches/leaves': <CoachLeavesPage />,
  'evaluations': <OperationsHubPage initialTab="evaluations" fixed />,
  'my/pending': <PendingConfirmationsPage />,
  'my/courses': <MyCoursesPage />,
  'my/calendar': <MyCalendarPage />,
  'my/evaluations': <OperationsHubPage initialTab="evaluations" fixed coachView />,
  'my/leaves': <MyLeavesPage />,
  'my/leaves/apply': <ApplyLeavePage />,
  'course-types': <CourseTypesPage />,
  'pricing': <PricingPage />,
  'resorts': <ResortsPage />,
  'payment-settings': <PaymentSettingsPage section="accounts" />,
  'payroll/rules': <OperationsHubPage initialTab="payroll-rules" fixed />,
  'payroll': <OperationsHubPage initialTab="payroll" fixed />,
  'payroll/incentives': <OperationsHubPage initialTab="staff-incentives" fixed />,
  'payroll/documents': <OperationsHubPage initialTab="payroll-documents" fixed />,
  'my/payroll': <MyPayrollPage />,
  'discounts': <DiscountsPage />,
  'cms/offers': <SiteContentPage initialGroup="news" section="site_campaigns" />,
  'social-sync': <SocialSyncPage />,
  'cms/homepage': <SiteContentPage initialGroup="homepage" section="site_home" />,
  'cms/courses': <SiteContentPage initialGroup="courses" section="site_courses" />,
  'cms/photography': <SiteContentPage initialGroup="photography" section="site_photography" />,
  'cms/guides': <SiteContentPage initialGroup="guides" section="site_guides" />,
  'cms/news': <SiteContentPage initialGroup="news" section="site_news" />,
  'cms/recruitment': <RecruitmentPage />,
  'cms/about': <SiteContentPage initialGroup="about" section="site_about" />,
  'cms/coaches': <CoachEditorPage />,
  'reviews/manual': <SiteContentPage contentTypes={REVIEW_TYPES} />,
  'media': <SiteContentPage initialGroup="photography" contentTypes={MEDIA_TYPES} />,
  'cms/tracking': <SiteContentPage initialGroup="homepage" section="site_tracking" />,
  'cms/structure': <SiteContentPage section="site_structure" />,
  'campuses': <CampusesPage />,
  'staff': <StaffPermissionsPage />,
  'cms/policies': <SiteContentPage initialGroup="membership" section="checkout_policies" />,
  'booking-form-settings': <PaymentSettingsPage section="booking-form" />,
  'system/support': <FrontendSupportPage />,
}

// Existing bookmarks continue to open the owning tab and its permission guard.
const legacyPaths: Record<string, ConsolePath> = {
  'cms/resorts': 'cms/courses',
  'cms/faq': 'cms/guides',
  'cms/articles': 'cms/guides',
  'reviews/google': 'reviews/manual',
}

export default function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        {consoleNavigation.flatMap(group => group.pages.map(page => (
          <Route key={page.path} element={<RoleGuard page={page} />}>
            {page.path ? <Route path={page.path} element={pages[page.path]} /> : <Route index element={pages['']} />}
          </Route>
        )))}
        {Object.entries(legacyPaths).map(([path, destination]) => (
          <Route key={path} path={path} element={<Navigate to={`../${destination}`} replace />} />
        ))}
      </Route>
    </Routes>
  )
}

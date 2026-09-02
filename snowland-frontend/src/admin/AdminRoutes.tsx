import { Routes, Route } from 'react-router-dom'
import AdminLayout from './layout/AdminLayout'
import RoleGuard from './components/RoleGuard'
import DashboardPage from './pages/DashboardPage'
import CoachesPage from './pages/CoachesPage'
import ResortsPage from './pages/ResortsPage'
import CourseTypesPage from './pages/CourseTypesPage'
import PricingPage from './pages/PricingPage'
import DiscountsPage from './pages/DiscountsPage'
import OrdersPage from './pages/OrdersPage'
import CustomersPage from './pages/CustomersPage'
import SchedulingPage from './pages/SchedulingPage'
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

export default function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        {/* 儀表板：manager 才能看 */}
        <Route element={<RoleGuard requireManager />}>
          <Route element={<RoleGuard permission="analytics" />}>
            <Route index element={<DashboardPage />} />
          </Route>

          {/* 營運管理 */}
          <Route element={<RoleGuard permission="orders" />}>
            <Route path="orders" element={<OrdersPage />} />
          </Route>
          <Route element={<RoleGuard permission="scheduling" />}>
            <Route path="scheduling" element={<SchedulingPage />} />
          </Route>
          <Route element={<RoleGuard permission="customers" />}>
            <Route path="customers" element={<CustomersPage />} />
          </Route>
          <Route element={<RoleGuard permission="chat_support" />}>
            <Route path="chat-support" element={<ChatSupportPage />} />
          </Route>

          {/* 基本設定 */}
          <Route element={<RoleGuard permission="coaches" />}>
            <Route path="coaches" element={<CoachesPage />} />
            <Route path="coaches/leaves" element={<CoachLeavesPage />} />
          </Route>
          <Route element={<RoleGuard permission="resorts" />}>
            <Route path="resorts" element={<ResortsPage />} />
          </Route>
          <Route element={<RoleGuard permission="course_types" />}>
            <Route path="course-types" element={<CourseTypesPage />} />
          </Route>
          <Route element={<RoleGuard permission="pricing" />}>
            <Route path="pricing" element={<PricingPage />} />
          </Route>
          <Route element={<RoleGuard permission="discounts" />}>
            <Route path="discounts" element={<DiscountsPage />} />
          </Route>
          <Route element={<RoleGuard permission="staff" />}>
            <Route path="staff" element={<StaffPermissionsPage />} />
          </Route>
          <Route element={<RoleGuard permission="payment_settings" />}>
            <Route path="payment-settings" element={<PaymentSettingsPage />} />
          </Route>

          {/* CMS */}
          <Route element={<RoleGuard permission="cms" />}>
            <Route path="cms/homepage" element={<SiteContentPage initialGroup="homepage" />} />
            <Route path="cms/courses" element={<SiteContentPage initialGroup="courses" />} />
            <Route path="cms/photography" element={<SiteContentPage initialGroup="photography" />} />
            <Route path="cms/guides" element={<SiteContentPage initialGroup="guides" />} />
            <Route path="cms/news" element={<SiteContentPage initialGroup="news" />} />
            <Route path="cms/about" element={<SiteContentPage initialGroup="about" />} />
            <Route path="cms/coaches" element={<CoachEditorPage />} />
            <Route path="cms/resorts" element={<SiteContentPage initialGroup="courses" />} />
            <Route path="cms/offers" element={<SiteContentPage initialGroup="news" />} />
            <Route path="cms/faq" element={<SiteContentPage initialGroup="guides" />} />
            <Route path="cms/articles" element={<SiteContentPage initialGroup="guides" />} />
          </Route>

          {/* 評論與媒體 */}
          <Route element={<RoleGuard permission="reviews" />}>
            <Route path="reviews/google" element={<SiteContentPage initialGroup="homepage" />} />
            <Route path="reviews/manual" element={<SiteContentPage initialGroup="homepage" />} />
            <Route path="media" element={<SiteContentPage initialGroup="photography" />} />
          </Route>
        </Route>

        {/* 教練視角：coach 才能看 */}
        <Route element={<RoleGuard requireCoach />}>
          <Route path="my/pending" element={<PendingConfirmationsPage />} />
          <Route path="my/courses" element={<MyCoursesPage />} />
          <Route path="my/calendar" element={<MyCalendarPage />} />
          <Route path="my/leaves" element={<MyLeavesPage />} />
          <Route path="my/leaves/apply" element={<ApplyLeavePage />} />
        </Route>
      </Route>
    </Routes>
  )
}

import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { SignupPage } from '@/pages/SignupPage'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardOverviewPage } from '@/pages/DashboardOverviewPage'
import { PoliciesPage } from '@/pages/PoliciesPage'
import { SubmissionsPage } from '@/pages/SubmissionsPage'
import { EvidencePage } from '@/pages/EvidencePage'
import { UnifiedReviewPage } from '@/pages/UnifiedReviewPage'
import { AuditPage } from '@/pages/AuditPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { SettingsPage } from '@/pages/SettingsPage'

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Authenticated Workspace Application */}
          <Route path="/app" element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardOverviewPage />} />
              <Route path="policies" element={<PoliciesPage />} />
              <Route path="submissions" element={<SubmissionsPage />} />
              <Route path="submissions/:id" element={<SubmissionsPage />} />
              <Route path="evidence" element={<EvidencePage />} />
              <Route path="reviews" element={<UnifiedReviewPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App

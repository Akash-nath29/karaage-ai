import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Link, Outlet, Route, Routes, useNavigate } from 'react-router'

import { Avatar } from '@/components/avatar'
import { Button } from '@/components/ui/button'
import { ProfilePage } from '@/features/account/ProfilePage'
import { ProgressPage } from '@/features/assessments/ProgressPage'
import { useLogout, useMe, useResendVerification } from '@/features/auth/api'
import {
  ForgotPasswordPage,
  InvitePage,
  LoginPage,
  RegisterPage,
  RequireAuth,
  ResetPasswordPage,
  VerifyEmailPage,
} from '@/features/auth/AuthPages'
import { CoursePage } from '@/features/courses/CoursePage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { TopicPage } from '@/features/syllabus/TopicPage'
import { WorkspacePage } from '@/features/workspaces/WorkspacePage'
import { shouldRetry } from '@/lib/api'

// Pages that render markdown pull in KaTeX and the markdown pipeline (Mermaid loads later, per diagram): on demand.
const LessonPage = lazy(() => import('@/features/lessons/LessonPage').then((m) => ({ default: m.LessonPage })))
const TutorPage = lazy(() => import('@/features/tutor/TutorPage').then((m) => ({ default: m.TutorPage })))
const QuizPage = lazy(() => import('@/features/assessments/QuizPage').then((m) => ({ default: m.QuizPage })))
const ResultsPage = lazy(() => import('@/features/assessments/ResultsPage').then((m) => ({ default: m.ResultsPage })))
const QuestionBankPage = lazy(() => import('@/features/assessments/QuestionBankPage').then((m) => ({ default: m.QuestionBankPage })))
const later = (page: ReactNode) => <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>{page}</Suspense>

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: shouldRetry } } })

function AccountMenu() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  if (!me.data) return null
  return (
    <div className="flex items-center gap-3">
      <Link to="/profile" className="flex items-center gap-2 text-sm hover:underline">
        <Avatar person={me.data} />
        <span className="hidden sm:inline">{me.data.display_name}</span>
      </Link>
      <Button variant="ghost" size="sm" disabled={logout.isPending}
              onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}>
        Sign out
      </Button>
    </div>
  )
}

function VerifyBanner() {
  const me = useMe()
  const resend = useResendVerification()
  if (!me.data || me.data.email_verified) return null
  return (
    <div className="border-b bg-muted/50">
      <p className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-3 gap-y-1 px-6 py-2 text-sm">
        Confirm your email address: we sent a link to {me.data.email}.
        {resend.isSuccess ? (
          <span className="text-muted-foreground">Sent again.</span>
        ) : (
          <button className="underline" onClick={() => resend.mutate()} disabled={resend.isPending}>
            Send it again
          </button>
        )}
        {resend.error && <span role="alert" className="text-destructive">{resend.error.message}</span>}
      </p>
    </div>
  )
}

function Shell() {
  return (
    <>
      <header className="border-b">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
          <Link to="/" className="font-semibold">
            Karaage
          </Link>
          <AccountMenu />
        </div>
      </header>
      <VerifyBanner />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <Outlet />
      </main>
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/invite/:token" element={<InvitePage />} />
            <Route element={<RequireAuth><Outlet /></RequireAuth>}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/workspaces/:workspaceId" element={<WorkspacePage />} />
              <Route path="/courses/:courseId" element={<CoursePage />} />
              <Route path="/topics/:topicId" element={<TopicPage />} />
              <Route path="/lessons/:lessonId" element={later(<LessonPage />)} />
              <Route path="/tutor/:sessionId" element={later(<TutorPage />)} />
              <Route path="/quizzes/:quizId" element={later(<QuizPage />)} />
              <Route path="/attempts/:attemptId" element={later(<ResultsPage />)} />
              <Route path="/courses/:courseId/questions" element={later(<QuestionBankPage />)} />
              <Route path="/courses/:courseId/progress" element={<ProgressPage />} />
              <Route path="*" element={<p className="text-muted-foreground">Page not found.</p>} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

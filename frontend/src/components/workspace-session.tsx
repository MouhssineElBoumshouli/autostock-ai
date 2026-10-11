import { useEffect, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, signOut } from '@/api/client'
import type { SessionData } from '@/api/contracts'
import { LoginScreen } from '@/components/login-screen'

const SELECTED_COMPANY_KEY = 'autostock.selected-company'

export type WorkspaceSessionValue = {
  session: SessionData
  companyId: number
  onSwitchCompany: (companyId: number) => void
  onSignOut: () => void
}

function savedCompanyId() {
  const stored = Number(sessionStorage.getItem(SELECTED_COMPANY_KEY))
  return Number.isInteger(stored) && stored > 0 ? stored : undefined
}

export function WorkspaceSession({ children }: {
  children: (value: WorkspaceSessionValue) => ReactNode
}) {
  const queryClient = useQueryClient()
  const [companyId, setCompanyId] = useState<number | undefined>(savedCompanyId)
  const sessionQuery = useQuery({
    queryKey: ['session', companyId ?? 'current'],
    queryFn: () => api.session(companyId),
  })
  const selectedCompanyForbidden = Boolean(
    companyId
    && sessionQuery.isError
    && sessionQuery.error instanceof ApiError
    && sessionQuery.error.code === 'forbidden',
  )
  const fallbackSessionQuery = useQuery({
    queryKey: ['session', 'current-after-company-denied'],
    queryFn: () => api.session(),
    enabled: selectedCompanyForbidden,
  })

  useEffect(() => {
    if (selectedCompanyForbidden) {
      sessionStorage.removeItem(SELECTED_COMPANY_KEY)
    }
  }, [selectedCompanyForbidden])

  async function handleSignOut() {
    await signOut()
    sessionStorage.removeItem(SELECTED_COMPANY_KEY)
    queryClient.clear()
    setCompanyId(undefined)
  }

  function handleSignedIn() {
    sessionStorage.removeItem(SELECTED_COMPANY_KEY)
    queryClient.invalidateQueries({ queryKey: ['session'] })
    setCompanyId(undefined)
  }

  function handleSwitchCompany(nextCompanyId: number) {
    sessionStorage.setItem(SELECTED_COMPANY_KEY, String(nextCompanyId))
    setCompanyId(nextCompanyId)
  }

  if (sessionQuery.isPending && !selectedCompanyForbidden) {
    return <main className="route-loading" role="status">Connecting to your Odoo workspace…</main>
  }
  if (selectedCompanyForbidden && fallbackSessionQuery.isPending) {
    return <main className="route-loading" role="status">Returning to your current company…</main>
  }
  const activeSessionQuery = selectedCompanyForbidden ? fallbackSessionQuery : sessionQuery
  if (activeSessionQuery.isError || !activeSessionQuery.data) {
    if (activeSessionQuery.error instanceof ApiError && activeSessionQuery.error.code === 'unauthenticated') {
      return <LoginScreen onSignedIn={handleSignedIn} />
    }
    return (
      <main className="route-loading" role="alert">
        <strong>AutoStock could not open your Odoo session.</strong>
        <p>{activeSessionQuery.error?.message ?? 'The current company could not be loaded.'}</p>
        <button className="inline-retry-button" type="button" onClick={() => void activeSessionQuery.refetch()}>Try again</button>
      </main>
    )
  }

  const session = activeSessionQuery.data
  const selectedCompanyId = selectedCompanyForbidden || !companyId ? session.current_company.id : companyId
  if (!session.user.permissions.inventory) {
    const company = session.allowed_companies.find((item) => item.id === selectedCompanyId) ?? session.current_company
    return (
      <main className="login-shell">
        <section className="login-card" aria-labelledby="permission-title">
          <h1 className="login-title" id="permission-title">Inventory access is required</h1>
          <p className="login-copy">Your Odoo user can sign in, but does not have the Inventory access needed to view AutoStock data for {company.name}.</p>
          <p className="login-foot">Ask an Odoo administrator to review your user groups, then sign in again.</p>
          <button className="login-submit" type="button" onClick={() => void handleSignOut()}>Sign out</button>
        </section>
      </main>
    )
  }

  return children({
    session,
    companyId: selectedCompanyId,
    onSwitchCompany: handleSwitchCompany,
    onSignOut: () => void handleSignOut(),
  })
}

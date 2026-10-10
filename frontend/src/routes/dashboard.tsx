import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, friendlyError, signOut } from '@/api/client'
import { AppShell } from '@/components/app-shell'
import { LoginScreen } from '@/components/login-screen'
import {
  ForecastPanel, InsightCards, InventoryHealthPanel, KpiGrid, PanelError, RestockPanel,
} from '@/components/dashboard-panels'
import { Skeleton } from '@/components/ui/skeleton'
import { Boxes, CircleAlert, RefreshCw, WifiOff } from 'lucide-react'

function DashboardSkeleton() {
  return (
    <main className="page-content" aria-label="Loading dashboard" aria-busy="true">
      <div className="skeleton" style={{ width: 140, height: 32, marginBottom: 9 }} />
      <div className="skeleton" style={{ width: 300, height: 13, marginBottom: 24 }} />
      <div className="kpi-grid">
        {Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="kpi-card" />)}
      </div>
      <div className="analytics-grid">
        <Skeleton className="panel" style={{ height: 420 }} />
        <Skeleton className="panel" style={{ height: 420 }} />
      </div>
      <Skeleton className="panel insights-panel" style={{ height: 150, marginTop: 17 }} />
      <Skeleton className="panel restock-panel" style={{ height: 300 }} />
      <span className="sr-only" role="status">Loading live Odoo inventory and forecasting data.</span>
    </main>
  )
}

function StatusScreen({ title, message, onRetry, offline = false }: {
  title: string
  message: string
  onRetry: () => void
  offline?: boolean
}) {
  const Icon = offline ? WifiOff : CircleAlert
  return (
    <main className="error-shell">
      <section className="status-card" role="alert">
        <span className="status-icon"><Icon size={20} /></span>
        <h1>{title}</h1>
        <p>{message}</p>
        <button type="button" onClick={onRetry}>Try again</button>
      </section>
    </main>
  )
}

function AccessScreen({ onSignOut }: { onSignOut: () => void }) {
  return (
    <main className="error-shell">
      <section className="status-card" role="alert">
        <span className="status-icon permission-icon"><Boxes size={20} /></span>
        <h1>Inventory access needed</h1>
        <p>Your Odoo account does not have permission to view inventory. Ask an Odoo administrator to grant the appropriate inventory role.</p>
        <button type="button" onClick={onSignOut}>Sign out</button>
      </section>
    </main>
  )
}

export function DashboardPage() {
  const queryClient = useQueryClient()
  const [selectedCompanyId, setSelectedCompanyId] = useState<number>()
  const [warehouseSelection, setWarehouseSelection] = useState<{ companyId: number; id?: number }>()
  const [forecastHorizon, setForecastHorizon] = useState(30)
  const sessionQuery = useQuery({
    queryKey: ['session', selectedCompanyId ?? 'active'],
    queryFn: () => api.session(selectedCompanyId),
    retry: false,
    staleTime: 30_000,
  })
  const session = sessionQuery.data
  const companyId = session?.current_company.id
  const warehouseId = warehouseSelection && warehouseSelection.companyId === companyId ? warehouseSelection.id : undefined
  const hasInventoryAccess = session?.user.permissions.inventory === true
  const dashboardQuery = useQuery({
    queryKey: ['dashboard', companyId],
    queryFn: () => api.dashboard(companyId!),
    enabled: Boolean(companyId && hasInventoryAccess),
  })
  const restockQuery = useQuery({
    queryKey: ['dashboard-restock', companyId, warehouseId ?? 'all'],
    queryFn: () => api.restock(companyId!, warehouseId),
    enabled: Boolean(companyId && hasInventoryAccess),
  })
  const forecastQuery = useQuery({
    queryKey: ['dashboard-forecast', companyId, forecastHorizon],
    queryFn: () => api.forecast(companyId!, forecastHorizon),
    enabled: Boolean(companyId && hasInventoryAccess),
  })

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        document.querySelector<HTMLButtonElement>('[aria-label="Search inventory"]')?.click()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  async function refreshSession() {
    await sessionQuery.refetch()
  }

  async function onSignedIn() {
    await queryClient.invalidateQueries({ queryKey: ['session'] })
    await sessionQuery.refetch()
  }

  async function onSignOut() {
    await signOut()
    queryClient.clear()
    window.location.reload()
  }

  async function refreshDashboard() {
    await Promise.all([
      dashboardQuery.refetch(),
      restockQuery.refetch(),
      forecastQuery.refetch(),
    ])
  }

  if (sessionQuery.isPending) return <DashboardSkeleton />
  if (!session && sessionQuery.error) {
    if (sessionQuery.error instanceof ApiError && sessionQuery.error.code === 'unauthenticated') {
      return <LoginScreen onSignedIn={onSignedIn} />
    }
    return <StatusScreen
      title="Could not connect to your workspace"
      message={friendlyError(sessionQuery.error)}
      onRetry={refreshSession}
      offline={sessionQuery.error instanceof ApiError && sessionQuery.error.code === 'network'}
    />
  }
  if (!session) return <DashboardSkeleton />

  if (!hasInventoryAccess) return <AccessScreen onSignOut={onSignOut} />

  return (
    <AppShell
      session={session}
      selectedCompanyId={companyId!}
      onCompanyChange={(id) => {
        setWarehouseSelection({ companyId: id })
        setSelectedCompanyId(id)
        setForecastHorizon(30)
      }}
      onSignOut={onSignOut}
    >
      {dashboardQuery.isPending ? <DashboardSkeleton /> : dashboardQuery.error ? (
        <main className="page-content">
          <PanelError title="Dashboard data could not be loaded" message={friendlyError(dashboardQuery.error)} onRetry={() => void dashboardQuery.refetch()} />
        </main>
      ) : dashboardQuery.data ? (
        <main className="page-content">
          <div className="page-heading reference-heading">
            <div>
              <h1 className="page-title">Dashboard</h1>
              <p className="page-subtitle">AI-powered inventory intelligence for automotive parts</p>
            </div>
            <div className="dashboard-actions">
              <span className="snapshot-label">Updated {dashboardQuery.data.snapshot_at}</span>
              <button type="button" className="refresh-button" onClick={() => void refreshDashboard()}>
                <RefreshCw size={15} /> Refresh
              </button>
            </div>
          </div>

          <KpiGrid data={dashboardQuery.data} restock={restockQuery.data} />

          <div className="analytics-grid">
            {forecastQuery.data ? (
              <ForecastPanel forecast={forecastQuery.data} horizonDays={forecastHorizon} onHorizonChange={setForecastHorizon} />
            ) : forecastQuery.error ? (
              <PanelError title="Demand forecast could not be loaded" message={friendlyError(forecastQuery.error)} onRetry={() => void forecastQuery.refetch()} />
            ) : <Skeleton className="panel" style={{ height: 400 }} />}
            <InventoryHealthPanel data={dashboardQuery.data} />
          </div>

          <InsightCards data={dashboardQuery.data} forecast={forecastQuery.data} restock={restockQuery.data} />

          {restockQuery.data ? (
            <RestockPanel data={restockQuery.data} warehouseId={warehouseId} onWarehouseChange={(id) => setWarehouseSelection({ companyId: companyId!, id })} />
          ) : restockQuery.error ? (
            <div className="restock-panel"><PanelError title="Reorder recommendations could not be loaded" message={friendlyError(restockQuery.error)} onRetry={() => void restockQuery.refetch()} /></div>
          ) : <Skeleton className="panel restock-panel" style={{ height: 300 }} />}

          <p className="page-footnote">Live data from {dashboardQuery.data.company.name} in Odoo. Recommendations remain read-only.</p>
        </main>
      ) : <DashboardSkeleton />}
    </AppShell>
  )
}

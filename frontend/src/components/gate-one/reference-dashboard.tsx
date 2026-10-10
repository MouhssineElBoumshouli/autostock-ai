import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FileBarChart2 } from 'lucide-react'
import { ApiError, api, signOut } from '@/api/client'
import type { DashboardData, RestockData, RiskItem, SessionData } from '@/api/contracts'
import { LoginScreen } from '@/components/login-screen'
import { DashboardShell, DashboardDateRange, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import {
  ForecastCard, InsightsSection, InventoryHealthCard, KpiCards, ReorderTable,
  type DashboardMetric, type ForecastHorizon, type ForecastOption,
  type InsightAction, type RiskFilter,
} from '@/components/gate-one/dashboard-panels'
import { DetailSheet, type DashboardDrawer } from '@/components/gate-two/detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'

function scrollToTarget(id: string) {
  document.getElementById(id)?.scrollIntoView({
    block: 'start',
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
  })
}

function useDashboardNotice() {
  const [toast, setToast] = useState('')
  const toastTimer = useRef<number | null>(null)
  const showNotice = useCallback((message: string) => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    setToast(message)
    toastTimer.current = window.setTimeout(() => setToast(''), 3200)
  }, [])
  useEffect(() => () => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
  }, [])
  return { toast, showNotice }
}

function formatCount(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

function createKpis(dashboard: DashboardData, restock: RestockData): DashboardMetric[] {
  const health = dashboard.inventory_health
  const stockScope = health.complete
    ? 'Current company stock across all tracked parts'
    : `${formatCount(health.sampled_products)} of ${formatCount(health.total_tracked)} tracked parts counted`
  const restockScope = restock.coverage.complete
    ? `Across ${formatCount(restock.coverage.scanned_locations)} part locations`
    : `Checked ${formatCount(restock.coverage.scanned_locations)} of ${formatCount(restock.coverage.candidate_locations)} part locations`
  return [
    { label: 'Total SKUs', value: formatCount(dashboard.kpis.tracked_products), note: 'Active parts enabled for stock monitoring', tone: 'violet', icon: 'boxes', detail: 'The number of active, storable products enabled for AutoStock monitoring in this Odoo company.' },
    { label: 'In Stock', value: formatCount(dashboard.kpis.in_stock), note: stockScope, tone: 'green', icon: 'stock', detail: 'Parts with positive stock above their configured AutoStock safety stock in the current company summary.' },
    { label: 'Low Stock', value: formatCount(dashboard.kpis.low_stock), note: 'At or below configured safety stock', tone: 'amber', icon: 'low', detail: 'Parts with positive stock at or below their configured AutoStock safety stock.' },
    { label: 'Out of Stock', value: formatCount(dashboard.kpis.out_of_stock), note: 'No stock across the company', tone: 'red', icon: 'risk', detail: 'Tracked parts with no stock in any warehouse across the selected company.' },
    { label: 'Reorder Suggestions', value: formatCount(restock.summary.reorder_suggestions), note: restockScope, tone: 'violet', icon: 'review', detail: 'Read-only reorder quantities calculated by the Odoo stock-risk service from visible stock, supplier terms, and reorder policies.' },
  ]
}

function DataError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="dashboard-error panel" role="alert"><strong>Dashboard data could not be loaded</strong><p>{message}</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}

function PermissionPage({ session, companyId, onSignOut }: { session: SessionData; companyId: number; onSignOut: () => void }) {
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="permission-title">
        <h1 className="login-title" id="permission-title">Inventory access is required</h1>
        <p className="login-copy">Your Odoo user can sign in, but does not have the Inventory access needed to view AutoStock data for {company.name}.</p>
        <p className="login-foot">Ask an Odoo administrator to review your user groups, then sign in again.</p>
        <button className="login-submit" type="button" onClick={onSignOut}>Sign out</button>
      </section>
    </main>
  )
}

function SessionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <main className="route-loading" role="alert"><strong>AutoStock could not open your Odoo session.</strong><p>{message}</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></main>
}

export function DashboardPage() {
  const queryClient = useQueryClient()
  const [companyId, setCompanyId] = useState<number | undefined>()
  const sessionQuery = useQuery({
    queryKey: ['session', companyId ?? 'current'],
    queryFn: () => api.session(companyId),
  })

  async function handleSignOut() {
    await signOut()
    queryClient.clear()
    setCompanyId(undefined)
  }

  function handleSignedIn() {
    queryClient.invalidateQueries({ queryKey: ['session'] })
    setCompanyId(undefined)
  }

  if (sessionQuery.isPending) return <main className="route-loading" role="status">Connecting to your Odoo workspace…</main>
  if (sessionQuery.isError) {
    if (sessionQuery.error instanceof ApiError && sessionQuery.error.code === 'unauthenticated') {
      return <LoginScreen onSignedIn={handleSignedIn} />
    }
    return <SessionError message={sessionQuery.error.message} onRetry={() => void sessionQuery.refetch()} />
  }
  const session = sessionQuery.data
  const selectedCompanyId = companyId ?? session.current_company.id
  if (!session.user.permissions.inventory) {
    return <PermissionPage session={session} companyId={selectedCompanyId} onSignOut={() => void handleSignOut()} />
  }

  return (
    <ReferenceDashboard
      key={selectedCompanyId}
      session={session}
      companyId={selectedCompanyId}
      onSwitchCompany={setCompanyId}
      onSignOut={() => void handleSignOut()}
    />
  )
}

function ReferenceDashboard({ session, companyId, onSwitchCompany, onSignOut }: {
  session: SessionData
  companyId: number
  onSwitchCompany: (companyId: number) => void
  onSignOut: () => void
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchProduct, setSearchProduct] = useState<ProductSearchItem | null>(null)
  const [drawer, setDrawer] = useState<DashboardDrawer>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<DashboardSection>('dashboard')
  const [selectedForecast, setSelectedForecast] = useState<ForecastOption | null>(null)
  const [horizon, setHorizon] = useState<ForecastHorizon>(30)
  const [riskFilter, setRiskFilter] = useState<RiskFilter>('All')
  const [categoryFilter, setCategoryFilter] = useState('All categories')
  const { toast, showNotice } = useDashboardNotice()

  useEffect(() => {
    function handleGlobalSearchShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', handleGlobalSearchShortcut)
    return () => window.removeEventListener('keydown', handleGlobalSearchShortcut)
  }, [])

  const dashboardQuery = useQuery({
    queryKey: ['dashboard', companyId],
    queryFn: () => api.dashboard(companyId),
  })
  const restockQuery = useQuery({
    queryKey: ['restock-preview', companyId],
    queryFn: () => api.restock(companyId),
  })
  const forecastQuery = useQuery({
    queryKey: [
      'forecast-preview', companyId, horizon, selectedForecast?.key ?? 'latest',
      selectedForecast?.product_id ?? null, selectedForecast?.warehouse_id ?? null,
    ],
    queryFn: () => api.forecast(companyId, horizon, selectedForecast?.product_id, selectedForecast?.warehouse_id || undefined),
  })
  const quickViewQuery = useQuery({
    queryKey: ['product-quick-view', companyId, searchProduct?.id],
    queryFn: () => api.quickView(companyId, searchProduct!.id),
    enabled: searchProduct !== null,
  })

  const forecastOptions = forecastQuery.data?.options ?? []
  const selectedForecastOption = selectedForecast && forecastOptions.some((item) => item.key === selectedForecast.key)
    ? selectedForecast
    : forecastOptions[0] ?? null
  const quickViewDrawer: DashboardDrawer = searchProduct
    ? quickViewQuery.data?.product.id === searchProduct.id
      ? { type: 'product', product: quickViewQuery.data }
      : quickViewQuery.isError
        ? { type: 'product-error', name: searchProduct.name, message: quickViewQuery.error.message }
        : { type: 'product-loading', name: searchProduct.name }
    : null
  const activeDrawer = searchProduct ? quickViewDrawer : drawer

  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  const dashboard = dashboardQuery.data
  const restock = restockQuery.data
  const forecast = forecastQuery.data
  const dateRange = `Next ${horizon} days`
  const dashboardMetrics = useMemo(() => dashboard && restock ? createKpis(dashboard, restock) : [], [dashboard, restock])

  function navigateTo(section: DashboardSection) {
    setActiveSection(section)
    const target = section === 'dashboard' ? 'dashboard-top' : section === 'inventory' ? 'inventory-health' : 'forecast-panel'
    window.requestAnimationFrame(() => scrollToTarget(target))
  }

  function onUnavailable(label: string) {
    showNotice(`${label} is not available in this release.`)
  }

  function clearFilters() {
    setRiskFilter('All')
    setCategoryFilter('All categories')
  }

  function handleInsight(action: InsightAction) {
    if (action === 'review-parts') {
      setRiskFilter('All')
      setCategoryFilter('All categories')
      window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
      return
    }
    clearFilters()
    window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
  }

  function viewRestockList() {
    setDrawer(null)
    clearFilters()
    window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
  }

  function changeDateRange(value: string) {
    const match = value.match(/(7|30|60)/)
    if (match) {
      setSelectedForecast(null)
      setHorizon(Number(match[1]) as ForecastHorizon)
    }
  }

  const queryFailure = dashboardQuery.error ?? restockQuery.error
  const anyQueryPending = dashboardQuery.isPending || restockQuery.isPending
  const refreshDashboard = () => {
    void dashboardQuery.refetch()
    void restockQuery.refetch()
  }

  return (
    <>
      <DashboardShell
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((value) => !value)}
        activeSection={activeSection}
        onNavigate={navigateTo}
        onUnavailable={onUnavailable}
        onOpenSearch={() => setSearchOpen(true)}
        mobileNavOpen={mobileNavOpen}
        onMobileNavChange={setMobileNavOpen}
        session={session}
        companyId={companyId}
        onSwitchCompany={onSwitchCompany}
        onSignOut={onSignOut}
      >
        <main className="page-content" id="dashboard-top">
          <div className="page-heading">
            <div>
              <h1>Dashboard</h1>
              <p>Live Odoo inventory and demand for {company.name}</p>
            </div>
            <div className="dashboard-heading-actions">
              <DashboardDateRange value={dateRange} onChange={changeDateRange} />
              <button className="report-control" type="button" disabled title="Reports are not available yet">
                <FileBarChart2 size={15} aria-hidden="true" />Generate Report
              </button>
            </div>
          </div>

          {queryFailure ? <DataError message={queryFailure.message} onRetry={refreshDashboard} /> : anyQueryPending || !dashboard || !restock ? (
            <div className="dashboard-loading" role="status">Loading your company’s inventory and recommendations…</div>
          ) : (
            <>
              <KpiCards metrics={dashboardMetrics} />

              <div className="analytics-grid">
                <ForecastCard
                  forecast={forecast}
                  options={forecastOptions}
                  selectedKey={selectedForecastOption?.key ?? null}
                  horizon={horizon}
                  onProductChange={(key) => setSelectedForecast(forecastOptions.find((option) => option.key === key) ?? null)}
                  onHorizonChange={(value) => { setSelectedForecast(null); setHorizon(value) }}
                  state={forecastQuery.isError ? 'error' : forecastQuery.isPending ? 'loading' : 'ready'}
                  onRetry={() => void forecastQuery.refetch()}
                />
                <InventoryHealthCard health={dashboard.inventory_health} onShowDetails={() => setDrawer({ type: 'health' })} />
              </div>

              <InsightsSection insights={restock.insights} onAction={handleInsight} onShowAll={() => setDrawer({ type: 'insights' })} />
              <ReorderTable
                products={restock.items}
                riskFilter={riskFilter}
                categoryFilter={categoryFilter}
                coverage={restock.coverage}
                onRiskFilterChange={setRiskFilter}
                onCategoryFilterChange={setCategoryFilter}
                onSeeAll={() => setDrawer({ type: 'recommendations' })}
                onOpenProduct={(product) => setDrawer({ type: 'recommendation', product })}
                state="ready"
                errorMessage=""
                onRetry={refreshDashboard}
                onClearFilters={clearFilters}
              />
            </>
          )}
        </main>
      </DashboardShell>

      <ProductSearchDialog
        open={searchOpen}
        onOpenChange={setSearchOpen}
        companyId={companyId}
        onSelectProduct={(product) => { setSearchProduct(product); setDrawer(null); setSearchOpen(false) }}
      />
      <DetailSheet
        drawer={activeDrawer}
        health={dashboard?.inventory_health}
        restock={restock}
        insights={restock?.insights}
        onRetryProduct={() => void quickViewQuery.refetch()}
        onOpenChange={(open) => { if (!open) { setDrawer(null); setSearchProduct(null) } }}
        onOpenRecommendation={(product: RiskItem) => setDrawer({ type: 'recommendation', product })}
        onGoToRestock={viewRestockList}
      />
      {toast && <div className="dashboard-toast" role="status">{toast}</div>}
      <span className="sr-only" aria-live="polite" data-testid="forecast-selection-status">
        {forecast?.status === 'available'
          ? `Showing ${forecast.forecast.product_name} for the next ${horizon} days.`
          : forecast?.message ?? `Loading demand forecast for the next ${horizon} days.`}
      </span>
    </>
  )
}

export function DashboardEntry() {
  return <DashboardPage />
}

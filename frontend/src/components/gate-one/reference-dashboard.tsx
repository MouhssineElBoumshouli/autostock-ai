import { useEffect, useMemo, useRef, useState } from 'react'
import { FileBarChart2 } from 'lucide-react'
import { DashboardShell, DashboardDateRange, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import {
  ForecastCard, InsightsSection, InventoryHealthCard, KpiCards, ReorderTable,
  type DashboardFixtureState, type InsightAction, type RiskFilter,
} from '@/components/gate-one/dashboard-panels'
import { DetailSheet, type DashboardDrawer } from '@/components/gate-two/detail-sheet'
import { ProductSearchDialog } from '@/components/gate-two/product-search-dialog'
import { developmentDashboardFixture } from '@/data/development-dashboard-fixture'
import {
  dateRangeFixtures, interactiveProducts,
  type ForecastHorizon, type InteractiveProduct,
} from '@/data/gate-two-fixtures'

function readFixtureState(): DashboardFixtureState {
  const requested = new URLSearchParams(window.location.search).get('fixtureState')
  return requested === 'loading' || requested === 'empty' || requested === 'error' ? requested : 'ready'
}

function scrollToTarget(id: string) {
  document.getElementById(id)?.scrollIntoView({
    block: 'start',
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
  })
}

export function ReferenceDashboard() {
  const [searchOpen, setSearchOpen] = useState(false)
  const [pendingProduct, setPendingProduct] = useState<InteractiveProduct | null>(null)
  const [drawer, setDrawer] = useState<DashboardDrawer>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<DashboardSection>('dashboard')
  const [productSku, setProductSku] = useState('BP-001')
  const [horizon, setHorizon] = useState<ForecastHorizon>(30)
  const [riskFilter, setRiskFilter] = useState<RiskFilter>('All')
  const [categoryFilter, setCategoryFilter] = useState('All categories')
  const [dateRange, setDateRange] = useState(developmentDashboardFixture.period)
  const [fixtureState, setFixtureState] = useState<DashboardFixtureState>(readFixtureState)
  const [toast, setToast] = useState('')
  const toastTimer = useRef<number | null>(null)

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  useEffect(() => {
    if (!pendingProduct || searchOpen) return
    const timer = window.setTimeout(() => {
      setDrawer({ type: 'product', product: pendingProduct })
      setPendingProduct(null)
    }, 160)
    return () => window.clearTimeout(timer)
  }, [pendingProduct, searchOpen])

  useEffect(() => () => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
  }, [])

  const filteredProducts = useMemo(() => interactiveProducts.filter((product) => (
    (riskFilter === 'All' || product.risk === riskFilter)
    && (categoryFilter === 'All categories' || product.category === categoryFilter)
  )), [categoryFilter, riskFilter])

  function showNotice(message: string) {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    setToast(message)
    toastTimer.current = window.setTimeout(() => setToast(''), 3200)
  }

  function navigateTo(section: DashboardSection) {
    setActiveSection(section)
    const target = section === 'dashboard' ? 'dashboard-top' : section === 'inventory' ? 'inventory-health' : 'forecast-panel'
    window.requestAnimationFrame(() => scrollToTarget(target))
  }

  function openSearchResult(product: InteractiveProduct) {
    setPendingProduct(product)
    setSearchOpen(false)
  }

  function changeDateRange(value: string) {
    setDateRange(value)
    const option = dateRangeFixtures.find((item) => item.value === value)
    if (option) setHorizon(option.horizon)
  }

  function clearFixtureState() {
    setFixtureState('ready')
    const url = new URL(window.location.href)
    url.searchParams.delete('fixtureState')
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
  }

  function clearFilters() {
    setRiskFilter('All')
    setCategoryFilter('All categories')
    if (fixtureState === 'empty') clearFixtureState()
  }

  function handleInsight(action: InsightAction) {
    if (action === 'review-parts') {
      setRiskFilter('High')
      setCategoryFilter('All categories')
      window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
      showNotice('Showing the highest-priority sample parts.')
      return
    }
    if (action === 'view-reorder') {
      clearFilters()
      window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
      return
    }
    setProductSku('BP-001')
    setHorizon(30)
    window.requestAnimationFrame(() => scrollToTarget('forecast-panel'))
  }

  function viewRestockList() {
    setDrawer(null)
    clearFilters()
    window.requestAnimationFrame(() => scrollToTarget('reorder-panel'))
  }

  return (
    <>
      <DashboardShell
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((value) => !value)}
        activeSection={activeSection}
        onNavigate={navigateTo}
        onUnavailable={(label) => showNotice(`${label} is not part of this preview yet.`)}
        onOpenSearch={() => setSearchOpen(true)}
        mobileNavOpen={mobileNavOpen}
        onMobileNavChange={setMobileNavOpen}
      >
        <main className="page-content" id="dashboard-top">
          <div className="page-heading">
            <div>
              <h1>Dashboard</h1>
              <p>AI-powered inventory intelligence for automotive parts</p>
            </div>
            <div className="dashboard-heading-actions">
              <DashboardDateRange value={dateRange} onChange={changeDateRange} />
              <button className="report-control" type="button" disabled title="Report generation is not included in this preview">
                <FileBarChart2 size={15} aria-hidden="true" />Generate Report
              </button>
            </div>
          </div>

          <KpiCards />

          <div className="analytics-grid">
            <ForecastCard
              productSku={productSku}
              horizon={horizon}
              onProductChange={setProductSku}
              onHorizonChange={setHorizon}
              fixtureState={fixtureState}
              onRetry={clearFixtureState}
            />
            <InventoryHealthCard onShowDetails={() => setDrawer({ type: 'health' })} />
          </div>

          <InsightsSection onAction={handleInsight} onShowAll={() => setDrawer({ type: 'insights' })} />
          <ReorderTable
            products={filteredProducts}
            riskFilter={riskFilter}
            categoryFilter={categoryFilter}
            onRiskFilterChange={setRiskFilter}
            onCategoryFilterChange={setCategoryFilter}
            onSeeAll={() => setDrawer({ type: 'recommendations' })}
            onOpenProduct={(product) => setDrawer({ type: 'recommendation', product })}
            fixtureState={fixtureState}
            onRetry={clearFixtureState}
            onClearFilters={clearFilters}
          />
        </main>
      </DashboardShell>

      <ProductSearchDialog open={searchOpen} onOpenChange={setSearchOpen} onSelectProduct={openSearchResult} />
      <DetailSheet
        drawer={drawer}
        onOpenChange={(open) => { if (!open) setDrawer(null) }}
        onOpenRecommendation={(product) => setDrawer({ type: 'recommendation', product })}
        onGoToRestock={viewRestockList}
      />
      {toast && <div className="fixture-toast" role="status">{toast}</div>}
      <span className="sr-only" aria-live="polite" data-testid="forecast-selection-status">
        Showing {interactiveProducts.find((product) => product.sku === productSku)?.name ?? 'selected part'} for the next {horizon} days.
      </span>
    </>
  )
}

import { CalendarDays, ChevronDown, FileBarChart2 } from 'lucide-react'
import { DashboardShell } from '@/components/gate-one/dashboard-shell'
import {
  ForecastCard, InsightsSection, InventoryHealthCard, KpiCards, ReorderTable,
} from '@/components/gate-one/dashboard-panels'
import { developmentDashboardFixture } from '@/data/development-dashboard-fixture'

export function ReferenceDashboard() {
  return (
    <DashboardShell>
      <main className="page-content">
        <div className="page-heading">
          <div>
            <h1>Dashboard</h1>
            <p>AI-powered inventory intelligence for automotive parts</p>
          </div>
          <div className="dashboard-heading-actions" aria-hidden="true">
            <span className="date-range-control"><CalendarDays size={16} />{developmentDashboardFixture.period}<ChevronDown size={14} /></span>
            <span className="report-control"><FileBarChart2 size={15} />Generate Report</span>
          </div>
        </div>

        <KpiCards />

        <div className="analytics-grid">
          <ForecastCard />
          <InventoryHealthCard />
        </div>

        <InsightsSection />
        <ReorderTable />
      </main>
    </DashboardShell>
  )
}

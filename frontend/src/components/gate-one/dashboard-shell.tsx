import type { ReactNode } from 'react'
import {
  ArrowRight, Bell, Bot, Boxes, Building2, CarFront, ChartNoAxesCombined,
  ChevronDown, ClipboardList, FileBarChart2, House, Menu, Search, Sparkles,
  Users, Warehouse, type LucideIcon,
} from 'lucide-react'

type NavigationItem = { label: string; icon: LucideIcon; active?: boolean }

const workspaceLinks: NavigationItem[] = [
  { label: 'Dashboard', icon: House, active: true },
  { label: 'Inventory', icon: Boxes },
  { label: 'Warehouses', icon: Warehouse },
  { label: 'Suppliers', icon: Building2 },
  { label: 'Purchase Orders', icon: ClipboardList },
  { label: 'Forecasts', icon: ChartNoAxesCombined },
  { label: 'Reports', icon: FileBarChart2 },
  { label: 'AI Assistant', icon: Bot },
]

const operationLinks: NavigationItem[] = [
  { label: 'Customers', icon: Users },
  { label: 'Vehicles / Fitment', icon: CarFront },
]

function AutoStockMark() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="gate-one-mark" x1="4" y1="4" x2="35" y2="36" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8159ff" />
          <stop offset="1" stopColor="#582fe2" />
        </linearGradient>
      </defs>
      <path d="M20 3.5 36.1 32.2a2.2 2.2 0 0 1-1.9 3.3h-7.1L20 22.9l-7.1 12.6H5.8a2.2 2.2 0 0 1-1.9-3.3L20 3.5Z" fill="url(#gate-one-mark)" />
      <path d="m20 11.3 5 8.7H15l5-8.7Z" fill="#fff" />
    </svg>
  )
}

function Brand() {
  return (
    <div className="brand-lockup" aria-label="AutoStock AI">
      <span className="brand-symbol"><AutoStockMark /></span>
      <span className="brand-wordmark">AutoStock <strong>AI</strong></span>
    </div>
  )
}

function NavigationItems({ items }: { items: NavigationItem[] }) {
  return (
    <div className="nav-list">
      {items.map(({ label, icon: Icon, active }) => (
        <span
          className={`nav-item${active ? ' is-active' : ''}`}
          aria-current={active ? 'page' : undefined}
          aria-disabled={active ? undefined : true}
          key={label}
          title={active ? undefined : `${label} is not part of this visual preview`}
        >
          <Icon size={18} strokeWidth={1.85} aria-hidden="true" />
          <span>{label}</span>
        </span>
      ))}
    </div>
  )
}

function Sidebar() {
  return (
    <aside className="sidebar-rail" aria-label="AutoStock workspace navigation">
      <Brand />
      <nav className="primary-navigation" aria-label="Workspace">
        <NavigationItems items={workspaceLinks} />
      </nav>
      <div className="sidebar-section-title">OPERATIONS</div>
      <nav aria-label="Operations">
        <NavigationItems items={operationLinks} />
      </nav>
      <div className="sidebar-bottom">
        <section className="assistant-promo" aria-label="AI Assistant preview">
          <span className="assistant-icon"><Bot size={20} strokeWidth={1.8} /></span>
          <h2>AI Assistant</h2>
          <p>Get instant insights about your inventory and demand trends.</p>
          <span className="assistant-cta" aria-hidden="true">Ask AI <ArrowRight size={13} /></span>
        </section>
        <div className="sidebar-profile">
          <span className="profile-avatar profile-avatar-photo" aria-hidden="true">AM</span>
          <span className="profile-copy"><strong>Alex Morgan</strong><small>Inventory Manager</small></span>
          <ChevronDown size={15} className="profile-chevron" aria-hidden="true" />
        </div>
      </div>
    </aside>
  )
}

function GlobalHeader() {
  return (
    <header className="global-header">
      <div className="global-header-main">
        <span className="mobile-menu-mark" aria-hidden="true"><Menu size={20} /></span>
        <div className="mobile-brand"><Brand /></div>
        <div className="global-search" aria-label="Global search preview">
          <Search size={17} strokeWidth={1.9} aria-hidden="true" />
          <span className="search-placeholder"><span className="desktop-search-copy">Search parts, SKUs, vehicles, or anything…</span><span className="mobile-search-copy">Search parts or SKUs…</span></span>
          <kbd>Ctrl K</kbd>
        </div>
      </div>
      <div className="global-header-actions">
        <span className="fixture-indicator" title="All displayed values are local development fixtures for visual review only">
          <Sparkles size={11} aria-hidden="true" /><span className="fixture-long">Visual preview · fixture data</span><span className="fixture-short">Fixture data</span>
        </span>
        <span className="notification-mark" aria-label="Notifications, visual preview only">
          <Bell size={19} strokeWidth={1.8} aria-hidden="true" /><span className="notification-count">3</span>
        </span>
        <span className="header-avatar" aria-label="Alex Morgan profile preview">AM</span>
        <ChevronDown className="header-chevron" size={15} aria-hidden="true" />
      </div>
    </header>
  )
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="dashboard-frame">
      <Sidebar />
      <div className="dashboard-main">
        <GlobalHeader />
        {children}
      </div>
    </div>
  )
}

import type { ReactNode } from 'react'
import {
  ArrowRight, Bell, Bot, Boxes, Building2, CalendarDays, CarFront, ChartNoAxesCombined,
  ChevronDown, ChevronLeft, ChevronRight, ClipboardList, FileBarChart2, House,
  Menu, Search, Sparkles, Users, Warehouse, type LucideIcon,
} from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { dateRangeFixtures, notificationFixtures } from '@/data/gate-two-fixtures'

export type DashboardSection = 'dashboard' | 'inventory' | 'forecast'

type NavigationItem = { label: string; icon: LucideIcon; section?: DashboardSection }

const workspaceLinks: NavigationItem[] = [
  { label: 'Dashboard', icon: House, section: 'dashboard' },
  { label: 'Inventory', icon: Boxes, section: 'inventory' },
  { label: 'Warehouses', icon: Warehouse },
  { label: 'Suppliers', icon: Building2 },
  { label: 'Purchase Orders', icon: ClipboardList },
  { label: 'Forecasts', icon: ChartNoAxesCombined, section: 'forecast' },
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

function NavigationItems({
  items,
  activeSection,
  onNavigate,
  onUnavailable,
  onAfterNavigate,
}: {
  items: NavigationItem[]
  activeSection: DashboardSection
  onNavigate: (section: DashboardSection) => void
  onUnavailable: (label: string) => void
  onAfterNavigate?: () => void
}) {
  return (
    <div className="nav-list">
      {items.map(({ label, icon: Icon, section }) => section ? (
        <button
          className={`nav-item${activeSection === section ? ' is-active' : ''}`}
          type="button"
          aria-current={activeSection === section ? 'page' : undefined}
          key={label}
          title={label}
          onClick={() => { onNavigate(section); onAfterNavigate?.() }}
        >
          <Icon size={18} strokeWidth={1.85} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ) : (
        <button
          className="nav-item is-unavailable"
          type="button"
          aria-disabled="true"
          key={label}
          title={`${label} is not part of this Dashboard preview`}
          onClick={() => { onUnavailable(label); onAfterNavigate?.() }}
        >
          <Icon size={18} strokeWidth={1.85} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  )
}

function Sidebar({
  collapsed,
  onToggleCollapsed,
  activeSection,
  onNavigate,
  onUnavailable,
}: {
  collapsed: boolean
  onToggleCollapsed: () => void
  activeSection: DashboardSection
  onNavigate: (section: DashboardSection) => void
  onUnavailable: (label: string) => void
}) {
  return (
    <aside className={`sidebar-rail${collapsed ? ' is-collapsed' : ''}`} aria-label="AutoStock workspace navigation">
      <Brand />
      <button
        className="sidebar-collapse-toggle"
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
      >
        {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
      </button>
      <nav className="primary-navigation" aria-label="Workspace">
        <NavigationItems items={workspaceLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} />
      </nav>
      <div className="sidebar-section-title">OPERATIONS</div>
      <nav aria-label="Operations">
        <NavigationItems items={operationLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} />
      </nav>
      <div className="sidebar-bottom">
        <section className="assistant-promo" aria-label="AI Assistant preview">
          <span className="assistant-icon"><Bot size={20} strokeWidth={1.8} /></span>
          <h2>AI Assistant</h2>
          <p>Get instant insights about your inventory and demand trends.</p>
          <span className="assistant-cta" title="The assistant is not included in this preview" aria-disabled="true">Ask AI <ArrowRight size={13} /></span>
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

export function DashboardDateRange({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="date-range-control" type="button" aria-label={`Date range: ${value}`}>
          <CalendarDays size={16} aria-hidden="true" /><span className="date-range-value">{value}</span><ChevronDown size={14} aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown">
        <DropdownMenuLabel>Dashboard date range</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {dateRangeFixtures.map((option) => (
          <DropdownMenuItem key={option.value} onSelect={() => onChange(option.value)}>
            <span className="menu-choice-check">{value === option.value ? '✓' : ''}</span>
            <span>{option.label}</span>
          </DropdownMenuItem>
        ))}
        <p className="menu-footnote">Fixture values remain illustrative.</p>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function NotificationsMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="notification-mark" type="button" aria-label="Notifications, 3 sample updates">
          <Bell size={19} strokeWidth={1.8} aria-hidden="true" /><span className="notification-count">3</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown notification-dropdown">
        <DropdownMenuLabel>Recent updates</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notificationFixtures.map((notification) => (
          <div className="notification-preview" key={notification.title}>
            <span className="notification-preview-dot" />
            <div><strong>{notification.title}</strong><p>{notification.detail}</p><small>{notification.time}</small></div>
          </div>
        ))}
        <p className="menu-footnote">Sample updates · no live notifications</p>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ProfileMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="profile-menu-trigger" type="button" aria-label="Profile menu for Alex Morgan">
          <span className="header-avatar" aria-hidden="true">AM</span><ChevronDown className="header-chevron" size={15} aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown profile-dropdown">
        <DropdownMenuLabel>Alex Morgan</DropdownMenuLabel>
        <div className="profile-menu-copy">Inventory Manager<br /><span>Local preview account</span></div>
        <DropdownMenuSeparator />
        <div className="profile-menu-status"><Sparkles size={13} aria-hidden="true" />Dashboard preview · fixture data</div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function GlobalHeader({
  onOpenSearch,
  onOpenMobileNav,
}: {
  onOpenSearch: () => void
  onOpenMobileNav: () => void
}) {
  return (
    <header className="global-header">
      <div className="global-header-main">
        <button className="mobile-menu-mark" type="button" onClick={onOpenMobileNav} aria-label="Open navigation menu"><Menu size={20} /></button>
        <div className="mobile-brand"><Brand /></div>
        <button className="global-search" type="button" aria-label="Search parts, SKUs, vehicles, or suppliers" onClick={onOpenSearch}>
          <Search size={17} strokeWidth={1.9} aria-hidden="true" />
          <span className="search-placeholder"><span className="desktop-search-copy">Search parts, SKUs, vehicles, or anything…</span><span className="mobile-search-copy">Search parts or SKUs…</span></span>
          <kbd>Ctrl K</kbd>
        </button>
      </div>
      <div className="global-header-actions">
        <span className="fixture-indicator" title="All displayed values are local development fixtures for visual review only">
          <Sparkles size={11} aria-hidden="true" /><span className="fixture-long">Visual preview · fixture data</span><span className="fixture-short">Fixture data</span>
        </span>
        <NotificationsMenu />
        <ProfileMenu />
      </div>
    </header>
  )
}

function MobileNavigationSheet({
  open,
  onOpenChange,
  activeSection,
  onNavigate,
  onUnavailable,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeSection: DashboardSection
  onNavigate: (section: DashboardSection) => void
  onUnavailable: (label: string) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="mobile-nav-sheet">
        <SheetHeader className="mobile-nav-heading">
          <Brand />
          <SheetTitle className="sr-only">AutoStock navigation</SheetTitle>
          <SheetDescription className="sr-only">Navigate sections available in this local Dashboard preview.</SheetDescription>
        </SheetHeader>
        <nav className="mobile-nav-list" aria-label="Workspace">
          <NavigationItems items={workspaceLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} onAfterNavigate={() => onOpenChange(false)} />
        </nav>
        <div className="sidebar-section-title mobile-nav-section-title">OPERATIONS</div>
        <nav className="mobile-nav-list" aria-label="Operations">
          <NavigationItems items={operationLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} onAfterNavigate={() => onOpenChange(false)} />
        </nav>
        <p className="mobile-nav-note">Only Dashboard, Inventory overview, and Forecast preview are available in this gate.</p>
      </SheetContent>
    </Sheet>
  )
}

export function DashboardShell({
  children,
  collapsed,
  onToggleCollapsed,
  activeSection,
  onNavigate,
  onUnavailable,
  onOpenSearch,
  mobileNavOpen,
  onMobileNavChange,
}: {
  children: ReactNode
  collapsed: boolean
  onToggleCollapsed: () => void
  activeSection: DashboardSection
  onNavigate: (section: DashboardSection) => void
  onUnavailable: (label: string) => void
  onOpenSearch: () => void
  mobileNavOpen: boolean
  onMobileNavChange: (open: boolean) => void
}) {
  return (
    <>
      <div className={`dashboard-frame${collapsed ? ' sidebar-collapsed' : ''}`}>
        <Sidebar collapsed={collapsed} onToggleCollapsed={onToggleCollapsed} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} />
        <div className="dashboard-main">
          <GlobalHeader onOpenSearch={onOpenSearch} onOpenMobileNav={() => onMobileNavChange(true)} />
          {children}
        </div>
      </div>
      <MobileNavigationSheet open={mobileNavOpen} onOpenChange={onMobileNavChange} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} />
    </>
  )
}

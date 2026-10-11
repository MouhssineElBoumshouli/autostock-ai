import type { ReactNode } from 'react'
import {
  ArrowRight, Bell, Bot, Boxes, Building2, CalendarDays, CarFront, ChartNoAxesCombined,
  ChevronDown, ChevronLeft, ChevronRight, ClipboardList, FileBarChart2, House,
  Menu, Search, Sparkles, Users, Warehouse, type LucideIcon,
} from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import type { SessionData } from '@/api/contracts'

export type DashboardSection = 'dashboard' | 'inventory' | 'warehouses' | 'suppliers' | 'forecast'

type NavigationItem = { label: string; icon: LucideIcon; section?: DashboardSection }

const workspaceLinks: NavigationItem[] = [
  { label: 'Dashboard', icon: House, section: 'dashboard' },
  { label: 'Inventory', icon: Boxes, section: 'inventory' },
  { label: 'Warehouses', icon: Warehouse, section: 'warehouses' },
  { label: 'Suppliers', icon: Building2, section: 'suppliers' },
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
          title={`${label} is not available in the current release`}
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
  user,
}: {
  collapsed: boolean
  onToggleCollapsed: () => void
  activeSection: DashboardSection
  onNavigate: (section: DashboardSection) => void
  onUnavailable: (label: string) => void
  user: SessionData['user']
}) {
  const initials = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join('').toUpperCase()
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
        <section className="assistant-promo" aria-label="AI Assistant">
          <span className="assistant-icon"><Bot size={20} strokeWidth={1.8} /></span>
          <h2>AI Assistant</h2>
          <p>Assistant tools are not available in this release.</p>
          <span className="assistant-cta" title="The assistant is not available yet" aria-disabled="true">Coming later <ArrowRight size={13} /></span>
        </section>
        <div className="sidebar-profile">
          <span className="profile-avatar" aria-hidden="true">{initials}</span>
          <span className="profile-copy"><strong>{user.name}</strong><small>{user.permissions.inventory_manager ? 'Inventory manager' : user.permissions.inventory ? 'Inventory access' : 'Workspace access'}</small></span>
          <ChevronDown size={15} className="profile-chevron" aria-hidden="true" />
        </div>
      </div>
    </aside>
  )
}

export function DashboardDateRange({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const options = ['Next 7 days', 'Next 30 days', 'Next 60 days']
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="date-range-control" type="button" aria-label={`Forecast period: ${value}`}>
          <CalendarDays size={16} aria-hidden="true" /><span className="date-range-value">{value}</span><ChevronDown size={14} aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown">
        <DropdownMenuLabel>Forecast period</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((option) => (
          <DropdownMenuItem key={option} onSelect={() => onChange(option)}>
            <span className="menu-choice-check">{value === option ? '✓' : ''}</span>
            <span>{option}</span>
          </DropdownMenuItem>
        ))}
        <p className="menu-footnote">Updates the demand forecast.</p>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function NotificationsMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="notification-mark" type="button" aria-label="Notifications">
          <Bell size={19} strokeWidth={1.8} aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown notification-dropdown">
        <DropdownMenuLabel>Recent updates</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="notification-empty">There are no notifications right now.</div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ProfileMenu({ session, companyId, onSwitchCompany, onSignOut }: {
  session: SessionData
  companyId: number
  onSwitchCompany: (companyId: number) => void
  onSignOut: () => void
}) {
  const initials = session.user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join('').toUpperCase()
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="profile-menu-trigger" type="button" aria-label={`Profile menu for ${session.user.name}`}>
          <span className="header-avatar" aria-hidden="true">{initials}</span><ChevronDown className="header-chevron" size={15} aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="header-dropdown profile-dropdown">
        <DropdownMenuLabel>{session.user.name}</DropdownMenuLabel>
        <div className="profile-menu-copy">{company.name}<br /><span>{session.user.permissions.inventory_manager ? 'Inventory manager' : session.user.permissions.inventory ? 'Inventory access' : 'Workspace access'}</span></div>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Company</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={String(companyId)} onValueChange={(value) => onSwitchCompany(Number(value))}>
          {session.allowed_companies.map((item) => (
            <DropdownMenuRadioItem key={item.id} value={String(item.id)}>{item.name}</DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSignOut}>Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function GlobalHeader({
  onOpenSearch,
  onOpenMobileNav,
  session,
  companyId,
  onSwitchCompany,
  onSignOut,
}: {
  onOpenSearch: () => void
  onOpenMobileNav: () => void
  session: SessionData
  companyId: number
  onSwitchCompany: (companyId: number) => void
  onSignOut: () => void
}) {
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  return (
    <header className="global-header">
      <div className="global-header-main">
        <button className="mobile-menu-mark" type="button" onClick={onOpenMobileNav} aria-label="Open navigation menu"><Menu size={20} /></button>
        <div className="mobile-brand"><Brand /></div>
        <button className="global-search" type="button" aria-label="Search parts, SKUs, suppliers, or references" onClick={onOpenSearch}>
          <Search size={17} strokeWidth={1.9} aria-hidden="true" />
          <span className="search-placeholder"><span className="desktop-search-copy">Search parts, SKUs, suppliers, or references…</span><span className="mobile-search-copy">Search parts or SKUs…</span></span>
          <kbd>Ctrl K</kbd>
        </button>
      </div>
      <div className="global-header-actions">
        {company.demo_environment && <span className="demo-indicator" title="This Odoo company is marked as a demo environment">
          <Sparkles size={11} aria-hidden="true" /><span className="demo-indicator-long">Demo environment</span><span className="demo-indicator-short">Demo</span>
        </span>}
        <NotificationsMenu />
        <ProfileMenu session={session} companyId={companyId} onSwitchCompany={onSwitchCompany} onSignOut={onSignOut} />
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
          <SheetDescription className="sr-only">Navigate the sections available in this AutoStock release.</SheetDescription>
        </SheetHeader>
        <nav className="mobile-nav-list" aria-label="Workspace">
          <NavigationItems items={workspaceLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} onAfterNavigate={() => onOpenChange(false)} />
        </nav>
        <div className="sidebar-section-title mobile-nav-section-title">OPERATIONS</div>
        <nav className="mobile-nav-list" aria-label="Operations">
          <NavigationItems items={operationLinks} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} onAfterNavigate={() => onOpenChange(false)} />
        </nav>
        <p className="mobile-nav-note">Some workspace sections are not available in this release.</p>
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
  session,
  companyId,
  onSwitchCompany,
  onSignOut,
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
  session: SessionData
  companyId: number
  onSwitchCompany: (companyId: number) => void
  onSignOut: () => void
}) {
  return (
    <>
      <div className={`dashboard-frame${collapsed ? ' sidebar-collapsed' : ''}`}>
        <Sidebar collapsed={collapsed} onToggleCollapsed={onToggleCollapsed} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} user={session.user} />
        <div className="dashboard-main">
          <GlobalHeader onOpenSearch={onOpenSearch} onOpenMobileNav={() => onMobileNavChange(true)} session={session} companyId={companyId} onSwitchCompany={onSwitchCompany} onSignOut={onSignOut} />
          {children}
        </div>
      </div>
      <MobileNavigationSheet open={mobileNavOpen} onOpenChange={onMobileNavChange} activeSection={activeSection} onNavigate={onNavigate} onUnavailable={onUnavailable} />
    </>
  )
}

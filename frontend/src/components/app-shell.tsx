import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import {
  Boxes, ChevronDown, LayoutDashboard, LogOut, Menu, Search,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { SessionData } from '@/api/contracts'

const ProductSearch = lazy(() => import('@/components/product-search').then((module) => ({ default: module.ProductSearch })))

type AppShellProps = {
  session: SessionData
  selectedCompanyId: number
  onCompanyChange: (id: number) => void
  onSignOut: () => void
  children: ReactNode
}

function CompanyMark({ company, className = '' }: { company: SessionData['current_company']; className?: string }) {
  return (
    <span className={`company-avatar ${className}`} aria-hidden="true">
      <img src={company.logo_url} alt="" onError={(event) => { event.currentTarget.style.display = 'none' }} />
      <span>{company.name.slice(0, 1).toUpperCase()}</span>
    </span>
  )
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark"><Boxes size={20} strokeWidth={2.1} /></span>
      <span>
        <span className="brand-name">AutoStock AI</span>
        <span className="brand-caption" style={{ display: 'block' }}>Inventory intelligence</span>
      </span>
    </div>
  )
}

function SidebarContents({ session, close, className = '' }: { session: SessionData; close?: () => void; className?: string }) {
  return (
    <aside className={`sidebar ${className}`}>
      <Brand />
      <div className="workspace-label">Workspace</div>
      <nav aria-label="Primary navigation">
        <Link to="/" className="nav-link" aria-current="page" onClick={close}>
          <LayoutDashboard size={17} strokeWidth={1.9} /> Dashboard
        </Link>
      </nav>
      <div className="sidebar-spacer" />
      <div className="connection-card" role="status" aria-label="Odoo connection active">
        <div className="connection-title"><span className="online-dot" /> Connected to Odoo</div>
        <p className="connection-caption">Live company inventory and forecasts</p>
      </div>
      <div className="sidebar-company">
        <CompanyMark company={session.current_company} />
        <div style={{ minWidth: 0 }}>
          <div className="sidebar-company-name">{session.current_company.name}</div>
          <div className="sidebar-company-caption">{session.user.name}</div>
        </div>
      </div>
    </aside>
  )
}

export function AppShell({ session, selectedCompanyId, onCompanyChange, onSignOut, children }: AppShellProps) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const company = session.current_company
  const initials = session.user.name.split(/\s+/).slice(0, 2).map((word) => word[0]).join('').toUpperCase()

  return (
    <div className="app-frame">
      <SidebarContents session={session} className="desktop" />
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <Button className="mobile-menu-button" variant="outline" size="icon" aria-label="Open navigation" onClick={() => setMobileMenuOpen(true)}>
                <Menu size={17} />
              </Button>
              <SheetContent side="left" className="mobile-sidebar">
                <SheetHeader className="sr-only">
                  <SheetTitle>AutoStock navigation</SheetTitle>
                  <SheetDescription>Open the dashboard and review Odoo connection details.</SheetDescription>
                </SheetHeader>
                <SidebarContents session={session} close={() => setMobileMenuOpen(false)} className="mobile-nav-shell" />
              </SheetContent>
            </Sheet>
            <div className="workspace-context"><strong>{company.name}</strong><span aria-hidden="true"> / </span>Workspace</div>
          </div>
          <div className="topbar-actions">
            <button className="search-trigger" type="button" aria-label="Search inventory" onClick={() => setSearchOpen(true)}>
              <Search size={15} /><span>Search parts</span><span className="keycap">Ctrl K</span>
            </button>
            <label className="sr-only" htmlFor="company-switcher">Current company</label>
            <select
              className="company-select"
              id="company-switcher"
              value={selectedCompanyId}
              aria-label="Current company"
              disabled={session.allowed_companies.length < 2}
              onChange={(event) => onCompanyChange(Number(event.target.value))}
            >
              {session.allowed_companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            {company.demo_environment && <span className="demo-pill" title={company.demo_environment_note || undefined}>Demo environment</span>}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="user-menu-button" type="button" aria-label={`Account menu for ${session.user.name}`}>
                  <span className="user-avatar">{initials}</span><ChevronDown className="user-chevron" size={13} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="account-menu">
                <DropdownMenuLabel>
                  <span className="account-name">{session.user.name}</span>
                  <span className="account-company">{company.name}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={onSignOut}><LogOut size={14} /> Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        {children}
      </div>
      {searchOpen && (
        <Suspense fallback={null}>
          <ProductSearch companyId={company.id} open={searchOpen} onOpenChange={setSearchOpen} />
        </Suspense>
      )}
    </div>
  )
}

import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import {
  ChevronDown, LayoutDashboard, LogOut, Menu, Search,
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

function AutoStockMark() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="autostock-mark-gradient" x1="4" x2="34" y1="4" y2="35" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#5f3ee8" />
        </linearGradient>
      </defs>
      <path d="M20 4 35 31.5c.8 1.5-.3 3.3-2 3.3h-6.3L20 22.3l-6.7 12.5H7c-1.7 0-2.8-1.8-2-3.3L20 4Z" fill="url(#autostock-mark-gradient)" />
      <path d="M20 11.2 25 20h-10l5-8.8Z" fill="#fff" opacity=".95" />
    </svg>
  )
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
      <span className="brand-mark"><AutoStockMark /></span>
      <span>
        <span className="brand-name">AutoStock <strong>AI</strong></span>
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
          <LayoutDashboard size={18} strokeWidth={1.9} /> Dashboard
        </Link>
      </nav>
      <div className="sidebar-spacer" />
      <div className="connection-card" role="status" aria-label="Odoo connection active">
        <div className="connection-title"><span className="online-dot" /> Connected to Odoo</div>
        <p className="connection-caption">Live inventory and planning data</p>
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
                <Menu size={18} />
              </Button>
              <SheetContent side="left" className="mobile-sidebar">
                <SheetHeader className="sr-only">
                  <SheetTitle>AutoStock navigation</SheetTitle>
                  <SheetDescription>Open AutoStock navigation and account details.</SheetDescription>
                </SheetHeader>
                <SidebarContents session={session} close={() => setMobileMenuOpen(false)} className="mobile-nav-shell" />
              </SheetContent>
            </Sheet>
            <button className="search-trigger" type="button" aria-label="Search inventory" onClick={() => setSearchOpen(true)}>
              <Search size={17} /><span>Search parts, SKUs, or OEM references…</span><span className="keycap">Ctrl K</span>
            </button>
          </div>
          <div className="topbar-actions">
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
                  <span className="user-avatar">{initials}</span><ChevronDown className="user-chevron" size={14} />
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

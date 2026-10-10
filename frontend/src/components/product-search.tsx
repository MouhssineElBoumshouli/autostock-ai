import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useDebounce } from '@/hooks/use-debounce'
import { api, friendlyError } from '@/api/client'
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { ArrowUpRight, Search, Tag } from 'lucide-react'

type ProductSearchProps = { companyId: number; open: boolean; onOpenChange: (open: boolean) => void }

export function ProductSearch({ companyId, open, onOpenChange }: ProductSearchProps) {
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search.trim(), 220)
  const results = useQuery({
    queryKey: ['product-search', companyId, debouncedSearch],
    queryFn: () => api.search(companyId, debouncedSearch),
    enabled: open && debouncedSearch.length >= 2,
    staleTime: 10_000,
    retry: false,
  })

  function close(nextOpen: boolean) {
    onOpenChange(nextOpen)
    if (!nextOpen) setSearch('')
  }

  function openProduct(productId: number) {
    window.location.assign(`/web#id=${productId}&model=product.product&view_type=form`)
  }

  const searchError = results.error ? friendlyError(results.error) : ''
  return (
    <CommandDialog open={open} onOpenChange={close} title="Search inventory" description="Find a product in the active Odoo company.">
      <CommandInput placeholder="Search by part name, SKU, or OEM reference…" value={search} onValueChange={setSearch} />
      <CommandList>
        {!debouncedSearch || debouncedSearch.length < 2 ? (
          <CommandEmpty>Type at least two characters to search the active catalog.</CommandEmpty>
        ) : results.isPending ? (
          <CommandEmpty>Searching Odoo inventory…</CommandEmpty>
        ) : searchError ? (
          <CommandEmpty>{searchError}</CommandEmpty>
        ) : !results.data?.results.length ? (
          <CommandEmpty>No matching parts were found in this company.</CommandEmpty>
        ) : (
          <CommandGroup heading="Products in this company">
            {results.data.results.map((product) => (
              <CommandItem key={product.id} value={`${product.name} ${product.sku} ${product.reference || ''}`} onSelect={() => openProduct(product.id)}>
                <Tag className="search-result-icon" size={15} />
                <span className="search-result-copy">
                  <strong>{product.name}</strong>
                  <small>{product.sku}{product.reference ? ` · ${product.reference}` : ''}</small>
                </span>
                <ArrowUpRight className="search-result-open" size={14} />
              </CommandItem>
            ))}
            {results.data.limited && <p className="search-limited">Showing the first 8 matching products.</p>}
          </CommandGroup>
        )}
      </CommandList>
      <div className="search-dialog-foot"><Search size={13} /> Search uses your Odoo company and inventory access.</div>
    </CommandDialog>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ArrowUpRight, Building2, PackageSearch } from 'lucide-react'
import { api } from '@/api/client'
import type { ProductSearchData } from '@/api/contracts'
import { useDebounce } from '@/hooks/use-debounce'
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from '@/components/ui/command'

type ProductSearchItem = ProductSearchData['results'][number]

function productCommandValue(product: ProductSearchItem) {
  return `${product.name} ${product.sku} ${product.reference || ''} ${product.supplier_names.join(' ')}`
}

type ProductSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  companyId: number
  onSelectProduct: (product: ProductSearchItem) => void
}

export function ProductSearchDialog({ open, onOpenChange, companyId, onSelectProduct }: ProductSearchDialogProps) {
  const [query, setQuery] = useState('')
  const [selectedCommandValue, setSelectedCommandValue] = useState('')
  const debouncedQuery = useDebounce(query.trim(), 250)
  const search = useQuery({
    queryKey: ['product-search', companyId, debouncedQuery],
    queryFn: () => api.search(companyId, debouncedQuery),
    enabled: open && debouncedQuery.length >= 2,
  })
  const results = search.data?.results ?? []
  const selectedValueIsCurrent = results.some((product) => productCommandValue(product) === selectedCommandValue)
  const commandValue = selectedValueIsCurrent
    ? selectedCommandValue
    : results.length ? productCommandValue(results[0]) : ''

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setQuery('')
      setSelectedCommandValue('')
    }
    onOpenChange(nextOpen)
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Search AutoStock"
      description="Find a part by name, SKU, OEM reference, or supplier."
      className="search-dialog-content"
      shouldFilter={false}
      commandValue={commandValue}
      onCommandValueChange={setSelectedCommandValue}
    >
      <CommandInput
        autoFocus
        aria-label="Search parts, SKUs, suppliers, and references"
        placeholder="Try a part name, SKU, OEM reference, or supplier…"
        onValueChange={(value) => { setQuery(value); setSelectedCommandValue('') }}
      />
      <CommandList className="global-search-results" aria-busy={search.isFetching}>
        {query.trim().length < 2 ? (
          <CommandEmpty>Type at least two characters to search this company’s catalog.</CommandEmpty>
        ) : query.trim() !== debouncedQuery ? (
          <div className="search-state" role="status">Searching this company’s catalog…</div>
        ) : search.isPending ? (
          <div className="search-state" role="status">Searching this company’s catalog…</div>
        ) : search.isError ? (
          <div className="search-state" role="alert">{search.error.message}</div>
        ) : (
          <>
            <CommandEmpty>No matching parts were found in this company’s catalog.</CommandEmpty>
            <CommandGroup heading="Parts">
              {search.data.results.map((product) => (
                <CommandItem
                  key={product.id}
                  value={productCommandValue(product)}
                  keywords={[product.category, ...product.supplier_names]}
                  onSelect={() => onSelectProduct(product)}
                  className="global-search-result"
                >
                  <span className="search-result-icon"><PackageSearch size={17} aria-hidden="true" /></span>
                  <span className="search-result-copy">
                    <strong>{product.name}</strong>
                    <small>{product.sku} · {product.category}</small>
                    {product.reference && <span>OEM reference · {product.reference}</span>}
                    {product.supplier_names.map((supplier) => (
                      <span key={supplier}><Building2 size={12} aria-hidden="true" />{supplier}</span>
                    ))}
                  </span>
                  <ArrowUpRight className="search-result-arrow" size={15} aria-hidden="true" />
                </CommandItem>
              ))}
              {search.data.limited && <p className="search-state">Showing the first matches. Refine your search to narrow the list.</p>}
            </CommandGroup>
          </>
        )}
      </CommandList>
      <div className="search-dialog-footer"><kbd>↑</kbd><kbd>↓</kbd><span>to move</span><kbd>↵</kbd><span>to open</span><kbd>esc</kbd><span>to close</span></div>
    </CommandDialog>
  )
}

export type { ProductSearchItem }

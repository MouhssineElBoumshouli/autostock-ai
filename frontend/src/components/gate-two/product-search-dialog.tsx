import { useState } from 'react'
import { ArrowUpRight, Building2, CarFront, PackageSearch } from 'lucide-react'
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from '@/components/ui/command'
import { interactiveProducts, type InteractiveProduct } from '@/data/gate-two-fixtures'

type ProductSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelectProduct: (product: InteractiveProduct) => void
}

export function ProductSearchDialog({ open, onOpenChange, onSelectProduct }: ProductSearchDialogProps) {
  const [query, setQuery] = useState('')

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) setQuery('')
    onOpenChange(nextOpen)
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Search AutoStock"
      description="Find a part by name, SKU, vehicle, or supplier. Results are local development fixtures."
      className="search-dialog-content"
    >
      <CommandInput
        autoFocus
        aria-label="Search parts, SKUs, vehicles, and suppliers"
        placeholder="Try a part, SKU, vehicle, or supplier…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList className="global-search-results">
        <CommandEmpty>No matching parts. Try a name, SKU, vehicle, or supplier.</CommandEmpty>
        <CommandGroup heading="Parts and vehicles">
          {interactiveProducts.map((product) => (
            <CommandItem
              key={product.sku}
              value={`${product.name} ${product.sku}`}
              keywords={[product.category, product.supplier, ...product.vehicles]}
              onSelect={() => onSelectProduct(product)}
              className="global-search-result"
            >
              <span className="search-result-icon"><PackageSearch size={17} aria-hidden="true" /></span>
              <span className="search-result-copy">
                <strong>{product.name}</strong>
                <small>{product.sku} · {product.category}</small>
                <span><CarFront size={12} aria-hidden="true" />{product.vehicles.join(' · ')}</span>
                <span><Building2 size={12} aria-hidden="true" />{product.supplier}</span>
              </span>
              <ArrowUpRight className="search-result-arrow" size={15} aria-hidden="true" />
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      <div className="search-dialog-footer"><kbd>↑</kbd><kbd>↓</kbd><span>to move</span><kbd>↵</kbd><span>to open</span><kbd>esc</kbd><span>to close</span></div>
    </CommandDialog>
  )
}

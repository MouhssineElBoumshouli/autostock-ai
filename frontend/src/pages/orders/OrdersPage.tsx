import { useSignedIn } from "@/components/SignedIn";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n";

import { PurchaseOrdersTab } from "./PurchaseOrdersTab";
import { WhatToOrderTab } from "./WhatToOrderTab";

// "What to order" (suggestions a manager approves) and "Purchase orders" (what became of them).
// Staff can look at both tabs but can't approve, reject, send or receive anything.
export function OrdersPage() {
  const canEdit = useSignedIn().user.role !== "staff";

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.orders} subtitle={t.orders.subtitle} />
      <Tabs defaultValue="toOrder">
        <TabsList>
          <TabsTrigger value="toOrder">{t.orders.tabs.toOrder}</TabsTrigger>
          <TabsTrigger value="purchaseOrders">{t.orders.tabs.purchaseOrders}</TabsTrigger>
        </TabsList>
        <TabsContent value="toOrder">
          <WhatToOrderTab canEdit={canEdit} />
        </TabsContent>
        <TabsContent value="purchaseOrders">
          <PurchaseOrdersTab canEdit={canEdit} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

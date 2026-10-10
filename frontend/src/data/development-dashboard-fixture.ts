/**
 * Illustrative values for Issue #22 Gate 1 visual review only.
 * These are not Odoo records, measured business results, or model validation.
 */
export type DevelopmentDashboardFixture = {
  period: string
  kpis: Array<{
    label: string
    value: string
    note: string
    trend: string
    trendDirection: 'up' | 'down'
    tone: 'violet' | 'green' | 'amber' | 'red'
    icon: 'boxes' | 'stock' | 'low' | 'risk' | 'accuracy'
  }>
  forecast: {
    product: string
    period: string
    yLabels: string[]
    xLabels: string[]
    confidencePath: string
    historyPath: string
    forecastPath: string
    historyDots: Array<{ x: number; y: number }>
    forecastStartX: number
  }
  health: {
    total: string
    segments: Array<{ label: string; count: string; percent: number; color: string }>
  }
  insights: Array<{
    title: string
    description: string
    action: string
    icon: 'trend' | 'reorder' | 'vehicle'
  }>
  reorder: Array<{
    name: string
    sku: string
    forecast: string
    growth: string
    stock: string
    suggested: string
    confidence: string
    risk: 'High' | 'Medium'
    icon: 'brake' | 'oil' | 'spark' | 'air' | 'battery'
  }>
}

export const developmentDashboardFixture = {
  period: 'Jan 1, 2025 – Mar 31, 2025',
  kpis: [
    { label: 'Total SKUs', value: '3,892', note: 'Across all categories', trend: '+8.4%', trendDirection: 'up', tone: 'violet', icon: 'boxes' },
    { label: 'In Stock', value: '2,841', note: '73% of total SKUs', trend: '+5.2%', trendDirection: 'up', tone: 'green', icon: 'stock' },
    { label: 'Low Stock', value: '682', note: '18% of total SKUs', trend: '−2.8%', trendDirection: 'down', tone: 'amber', icon: 'low' },
    { label: 'At Risk', value: '369', note: '9% may stock out soon', trend: '−1.6%', trendDirection: 'down', tone: 'red', icon: 'risk' },
    { label: 'Forecast Accuracy', value: '92.4%', note: 'Based on last 30 days', trend: '+12.3%', trendDirection: 'up', tone: 'violet', icon: 'accuracy' },
  ],
  forecast: {
    product: 'Brake Pads',
    period: '12 Weeks',
    yLabels: ['1,200', '900', '600', '300', '0'],
    xLabels: ['Jan 1', 'Jan 15', 'Jan 29', 'Feb 12', 'Feb 26', 'Mar 12', 'Mar 26', 'Apr 9'],
    confidencePath: 'M 435 90 C 485 83 515 76 555 68 S 630 50 690 35 L 690 146 C 640 143 605 140 555 139 S 485 139 435 128 Z',
    historyPath: 'M 0 133 C 22 122 32 106 57 112 S 82 129 105 118 S 138 80 165 87 S 199 118 225 98 S 259 68 285 84 S 317 118 345 111 S 378 101 405 108 S 425 116 435 118',
    forecastPath: 'M 435 118 C 470 113 482 101 510 104 S 548 99 570 91 S 608 84 630 85 S 666 68 690 57',
    historyDots: [
      { x: 0, y: 133 }, { x: 28, y: 117 }, { x: 57, y: 112 }, { x: 83, y: 125 },
      { x: 113, y: 112 }, { x: 165, y: 87 }, { x: 197, y: 111 }, { x: 225, y: 98 },
      { x: 285, y: 84 }, { x: 317, y: 116 }, { x: 345, y: 111 }, { x: 378, y: 101 },
    ],
    forecastStartX: 435,
  },
  health: {
    total: '3,892',
    segments: [
      { label: 'Healthy Stock', count: '2,841', percent: 73, color: 'green' },
      { label: 'Low Stock', count: '682', percent: 18, color: 'amber' },
      { label: 'Out of Stock', count: '369', percent: 9, color: 'red' },
    ],
  },
  insights: [
    {
      title: 'Increased Demand Predicted',
      description: 'Brake pads demand is expected to increase by 32% in the next 4 weeks due to seasonal service schedules.',
      action: 'Review Parts',
      icon: 'trend',
    },
    {
      title: 'Reorder Suggested',
      description: '12 SKUs are likely to stock out within 14 days. Consider placing purchase orders to avoid stockouts.',
      action: 'View Reorder List',
      icon: 'reorder',
    },
    {
      title: 'Trending Opportunity',
      description: 'Cabin air filters show 28% higher demand this spring. Consider increasing stock levels.',
      action: 'Explore Forecast',
      icon: 'vehicle',
    },
  ],
  reorder: [
    { name: 'Brake Pads (Front)', sku: 'BP-001', forecast: '420', growth: '+32%', stock: '80', suggested: '400', confidence: '94%', risk: 'High', icon: 'brake' },
    { name: 'Oil Filter', sku: 'OF-203', forecast: '380', growth: '+18%', stock: '120', suggested: '300', confidence: '89%', risk: 'Medium', icon: 'oil' },
    { name: 'Spark Plug', sku: 'SP-104', forecast: '300', growth: '+25%', stock: '60', suggested: '300', confidence: '87%', risk: 'High', icon: 'spark' },
    { name: 'Air Filter (Engine)', sku: 'AF-331', forecast: '260', growth: '+12%', stock: '45', suggested: '250', confidence: '85%', risk: 'High', icon: 'air' },
    { name: 'Car Battery (12V)', sku: 'BT-912', forecast: '180', growth: '+15%', stock: '20', suggested: '200', confidence: '82%', risk: 'Medium', icon: 'battery' },
  ],
} satisfies DevelopmentDashboardFixture

import { developmentDashboardFixture } from '@/data/development-dashboard-fixture'

export type InteractiveProduct = typeof developmentDashboardFixture.reorder[number] & {
  category: 'Brakes' | 'Filters' | 'Ignition' | 'Electrical'
  supplier: string
  leadTimeDays: number
  vehicles: string[]
  reason: string
  calculationNotes: string[]
}

export const interactiveProducts: InteractiveProduct[] = [
  {
    ...developmentDashboardFixture.reorder[0],
    category: 'Brakes', supplier: 'Northline Auto Supply', leadTimeDays: 5,
    vehicles: ['Honda Civic', 'Acura Integra'],
    reason: 'Expected demand is rising while current stock covers only a short part of the supplier wait.',
    calculationNotes: [
      'The suggested quantity is a typed development fixture value.',
      'A real recommendation would compare available stock with expected demand during the supplier lead time and the business reorder policy.',
      'No live inventory or supplier records are connected in this preview.',
    ],
  },
  {
    ...developmentDashboardFixture.reorder[1],
    category: 'Filters', supplier: 'MotorWorks Wholesale', leadTimeDays: 4,
    vehicles: ['Honda Civic', 'Toyota Corolla'],
    reason: 'This filter is moving steadily and the fixture stock level is below its suggested reorder point.',
    calculationNotes: [
      'The suggested quantity is a typed development fixture value.',
      'The display compares fixture stock and expected demand with a sample supplier lead time.',
      'No purchase order is created by this preview.',
    ],
  },
  {
    ...developmentDashboardFixture.reorder[2],
    category: 'Ignition', supplier: 'Summit Ignition Parts', leadTimeDays: 7,
    vehicles: ['Toyota Corolla', 'Honda CR-V'],
    reason: 'The fixture shows a higher expected demand trend and limited stock on hand.',
    calculationNotes: [
      'The suggested quantity is a typed development fixture value.',
      'The example highlights the expected demand trend and current fixture stock.',
      'No live reorder policy or Odoo stock calculation is used.',
    ],
  },
  {
    ...developmentDashboardFixture.reorder[3],
    category: 'Filters', supplier: 'ClearAir Automotive', leadTimeDays: 6,
    vehicles: ['Toyota Corolla', 'Honda Accord'],
    reason: 'A fixture demand increase and the supplier wait make this part worth reviewing soon.',
    calculationNotes: [
      'The suggested quantity is a typed development fixture value.',
      'The sample considers the displayed stock, demand trend and lead-time label as explanation only.',
      'The browser does not calculate a business reorder quantity.',
    ],
  },
  {
    ...developmentDashboardFixture.reorder[4],
    category: 'Electrical', supplier: 'Northstar Battery Co.', leadTimeDays: 8,
    vehicles: ['Ford F-150', 'Toyota Camry'],
    reason: 'Battery stock is low in this example, but its risk is lower than the high-priority parts above.',
    calculationNotes: [
      'The suggested quantity is a typed development fixture value.',
      'The risk label and quantity are prewritten in the development fixture.',
      'A real workflow would require an authorized reviewer before any purchasing action.',
    ],
  },
]

export type ForecastHorizon = 7 | 30 | 60

export type ForecastFixture = {
  yMaximum: number
  xLabels: string[]
  actual: number[]
  expected: number[]
  lowerRange: number[]
  upperRange: number[]
}

/** Static illustrative chart points used only by the Issue #24 Gate 2 prototype. */
export const forecastFixtures: Record<string, Record<ForecastHorizon, ForecastFixture>> = {
  'BP-001': {
    7: { yMaximum: 100, xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next'], actual: [22, 31, 27, 39, 36], expected: [36, 42, 52, 61], lowerRange: [29, 33, 38, 44], upperRange: [44, 52, 66, 78] },
    30: { yMaximum: 1200, xLabels: ['Jan 1', 'Jan 8', 'Jan 15', 'Jan 22', 'Jan 29', 'Feb 5', 'Feb 12', 'Feb 19'], actual: [180, 320, 340, 260, 360], expected: [360, 420, 530, 760], lowerRange: [300, 330, 410, 580], upperRange: [430, 540, 690, 920] },
    60: { yMaximum: 2400, xLabels: ['Jan 1', 'Jan 9', 'Jan 17', 'Jan 25', 'Feb 2', 'Feb 10', 'Feb 18', 'Feb 26'], actual: [400, 640, 700, 520, 720], expected: [720, 850, 1150, 1580], lowerRange: [600, 680, 900, 1120], upperRange: [890, 1080, 1450, 2030] },
  },
  'OF-203': {
    7: { yMaximum: 80, xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next'], actual: [18, 22, 20, 24, 21], expected: [21, 24, 30, 36], lowerRange: [17, 19, 23, 27], upperRange: [26, 31, 39, 48] },
    30: { yMaximum: 900, xLabels: ['Jan 1', 'Jan 8', 'Jan 15', 'Jan 22', 'Jan 29', 'Feb 5', 'Feb 12', 'Feb 19'], actual: [190, 250, 230, 280, 260], expected: [260, 300, 345, 420], lowerRange: [220, 245, 285, 330], upperRange: [320, 380, 430, 540] },
    60: { yMaximum: 1800, xLabels: ['Jan 1', 'Jan 9', 'Jan 17', 'Jan 25', 'Feb 2', 'Feb 10', 'Feb 18', 'Feb 26'], actual: [380, 470, 450, 530, 500], expected: [500, 590, 660, 800], lowerRange: [420, 480, 530, 620], upperRange: [610, 740, 850, 1030] },
  },
  'SP-104': {
    7: { yMaximum: 65, xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next'], actual: [10, 17, 12, 19, 16], expected: [16, 20, 26, 32], lowerRange: [12, 15, 19, 23], upperRange: [21, 27, 35, 43] },
    30: { yMaximum: 700, xLabels: ['Jan 1', 'Jan 8', 'Jan 15', 'Jan 22', 'Jan 29', 'Feb 5', 'Feb 12', 'Feb 19'], actual: [130, 180, 160, 220, 190], expected: [190, 230, 295, 380], lowerRange: [160, 185, 230, 285], upperRange: [235, 290, 380, 490] },
    60: { yMaximum: 1400, xLabels: ['Jan 1', 'Jan 9', 'Jan 17', 'Jan 25', 'Feb 2', 'Feb 10', 'Feb 18', 'Feb 26'], actual: [260, 340, 310, 390, 360], expected: [360, 440, 560, 720], lowerRange: [300, 350, 430, 540], upperRange: [450, 560, 700, 900] },
  },
  'AF-331': {
    7: { yMaximum: 60, xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next'], actual: [9, 13, 12, 16, 14], expected: [14, 18, 24, 30], lowerRange: [10, 13, 18, 22], upperRange: [19, 25, 32, 39] },
    30: { yMaximum: 600, xLabels: ['Jan 1', 'Jan 8', 'Jan 15', 'Jan 22', 'Jan 29', 'Feb 5', 'Feb 12', 'Feb 19'], actual: [100, 145, 130, 190, 165], expected: [165, 205, 265, 340], lowerRange: [135, 160, 205, 250], upperRange: [210, 255, 335, 440] },
    60: { yMaximum: 1200, xLabels: ['Jan 1', 'Jan 9', 'Jan 17', 'Jan 25', 'Feb 2', 'Feb 10', 'Feb 18', 'Feb 26'], actual: [200, 280, 250, 360, 320], expected: [320, 400, 520, 680], lowerRange: [270, 320, 410, 510], upperRange: [400, 510, 660, 850] },
  },
  'BT-912': {
    7: { yMaximum: 32, xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Next'], actual: [3, 7, 4, 9, 6], expected: [6, 9, 13, 18], lowerRange: [4, 6, 9, 12], upperRange: [9, 13, 19, 25] },
    30: { yMaximum: 400, xLabels: ['Jan 1', 'Jan 8', 'Jan 15', 'Jan 22', 'Jan 29', 'Feb 5', 'Feb 12', 'Feb 19'], actual: [70, 105, 90, 135, 110], expected: [110, 145, 190, 260], lowerRange: [90, 115, 150, 190], upperRange: [145, 185, 245, 330] },
    60: { yMaximum: 800, xLabels: ['Jan 1', 'Jan 9', 'Jan 17', 'Jan 25', 'Feb 2', 'Feb 10', 'Feb 18', 'Feb 26'], actual: [140, 200, 175, 260, 225], expected: [225, 300, 390, 520], lowerRange: [190, 240, 310, 400], upperRange: [290, 380, 500, 660] },
  },
}

export const dateRangeFixtures = [
  { label: 'Last 30 days', value: 'Nov 1, 2025 – Nov 30, 2025', horizon: 30 as const },
  { label: 'Last 60 days', value: 'Oct 1, 2025 – Nov 30, 2025', horizon: 60 as const },
  { label: 'This quarter', value: 'Oct 1, 2025 – Dec 31, 2025', horizon: 30 as const },
]

export const notificationFixtures = [
  { title: 'Brake pads need a review', detail: 'A demo reorder suggestion is marked high priority.', time: 'Today' },
  { title: 'Forecast preview updated', detail: 'The local sample view is ready to explore.', time: 'Yesterday' },
  { title: 'Low stock sample', detail: 'Oil Filter is included in the preview list.', time: 'Yesterday' },
]

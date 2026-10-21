// All English text shown to users. fr.ts and ar.ts have exactly the same shape (checked by `npm test`).

// The words an Ask answer is built from, already formatted by src/pages/ask/askSentence.ts.
export type AnswerWords = {
  subject: string; // "all parts", "Oil filter (3 parts)", "the Brakes category"
  Subject: string; // the same with a capital first letter, to start a sentence
  branch: string | null;
  period: string; // "this week"
  range: string; // "Oct 14 – Oct 20"
  pieces: string; // "5 pieces"
  money: string | null; // null for people who don't see money
  count: number;
  shownCount: string;
  name: string;
  sku: string;
  beforePieces: string;
  beforeRange: string;
  percent: number | null;
  days: string;
  daysLeft: string;
  low: string;
  high: string;
  madeFrom: string;
  madeOn: string;
  part: string;
  alertBranch: string;
  alert: string;
  orderNumber: string;
  supplier: string;
  words: string | null;
};

const inBranch = (branch: string | null) => (branch ? ` in ${branch}` : "");

export const en = {
  appName: "AutoStock AI",
  common: {
    close: "Close",
    cancel: "Cancel",
    tryAgain: "Try again",
    goHome: "Go to home",
    save: "Save",
    noAccess: "You don't have access to this page.",
    previous: "Previous",
    next: "Next",
    back: "Back",
    edit: "Edit",
    remove: "Remove",
    notSet: "Not set",
    showing: (from: string, to: string, total: string) => `${from}–${to} of ${total}`,
    pages: "Pages",
    clearFilters: "Clear filters",
    never: "Never",
    you: "you",
    showPassword: "Show password",
    hidePassword: "Hide password",
    pieces: (count: number, shown: string) => (count === 1 ? "1 piece" : `${shown} pieces`),
    days: (count: number, shown: string) => (count === 1 ? "1 day" : `${shown} days`),
  },
  states: {
    loadFailed: "We couldn't load this. Check your connection and try again.",
    somethingWrong: "Something went wrong. Try again.",
  },
  stock: {
    healthy: "Healthy",
    low: "Low stock",
    out: "Out of stock",
    inactive: "Inactive",
    running_out: "Running out",
    subtitle: "Every part, how many you have, and what needs attention.",
    importButton: "Import from Excel",
    stats: {
      all: "All parts",
      allNote: "Active parts in your shop",
      healthyNote: "Above their minimum",
      lowNote: "At or below their minimum",
      outNote: "Nothing left on the shelf",
      runningOutNote: "Expected to run out within 14 days",
    },
    runningOutSoon: "Running out",
    searchLabel: "Search parts",
    searchPlaceholder: "Search parts",
    closestParts: "No exact match. Closest parts:",
    outOfStockEquivalent: (quantity: string, brand: string) => `Out of stock. ${quantity} available from ${brand}.`,
    filters: {
      status: "Status",
      allStatuses: "All statuses",
      dead: "Dead stock (no sale in 90 days)",
      category: "Category",
      allCategories: "All categories",
      branch: "Branch",
      allBranches: "All branches",
      supplier: "Supplier",
      allSuppliers: "All suppliers",
      title: "Filters",
      openFilters: "Filters",
      openFiltersWithCount: (count: number) => `Filters (${count})`,
      done: "Done",
    },
    columns: {
      part: "Part",
      sku: "SKU",
      brand: "Brand",
      inStock: "In stock",
      minimum: "Minimum",
      status: "Status",
      supplier: "Supplier",
      next30Days: "Next 30 days",
      runsOutIn: "Runs out in",
    },
    sortBy: (column: string) => `Sort by ${column}`,
    emptyTitle: "No parts yet. Import your stock from an Excel file",
    emptyText: "Your parts list with prices and quantities, from Excel or CSV.",
    emptyStaff: "Ask your owner or manager to import the shop's stock.",
    noMatch: "No parts match these filters.",
    lowStockTitle: "Low stock",
    seeAllLow: "See all low stock",
    nothingLow: "Nothing is low right now.",
    runsOut: {
      alreadyOut: "Already out",
      overSixty: "Over 60 days",
      aboutDays: (days: string) => `About ${days} days`,
    },
    forecastStatus: {
      updated: (time: string) => `Forecasts updated ${time}`,
      never: "Forecasts have not been run yet.",
      updateNow: "Update now",
    },
  },
  demo: {
    banner: "Demo shop. Made-up data for testing and presentations.",
  },
  orders: {
    subtitle: "Decide what to order, grouped by supplier.",
    tabs: { toOrder: "What to order", purchaseOrders: "Purchase orders" },
    getSuggestions: "Get suggestions",
    updating: "Working it out…",
    lastRun: (time: string) => `Last worked out ${time}`,
    noRunYet: "Press “Get suggestions” to see what your shop needs.",
    emptyTitle: "Nothing to order today.",
    emptyText: "Your stock covers expected sales.",
    budget: {
      title: "Budget",
      label: "Budget for this run",
      placeholder: "No limit",
      help: "Lines that don't fit are moved to the list below, with why.",
      apply: "Apply",
      suggestedTotal: "Everything suggested",
      keptTotal: "Within budget",
    },
    statuses: {
      suggested: "Suggested",
      cut_by_budget: "Didn't fit budget",
      approved: "Approved",
      rejected: "Rejected",
    },
    columns: {
      part: "Part",
      branch: "Branch",
      inStock: "In stock",
      quantity: "Order",
      cost: "Cost",
      reason: "Why",
    },
    approve: "Approve",
    reject: "Reject",
    editQuantity: "Change quantity",
    saveQuantity: "Save",
    approveAllForSupplier: "Approve all for this supplier",
    noSupplier: "No supplier set. Add one in Settings to approve this line.",
    noSupplierGroup: "No supplier set",
    supplierTotal: (cost: string) => `Supplier total ${cost}`,
    grandTotal: "Total to order",
    didntFitBudget: "Didn't fit the budget",
    quantityError: "Enter a whole number of at least 1",
    approved: "Approved.",
    rejected: "Rejected.",
    approvedAll: (count: string) => `Approved ${count} lines.`,
    // Why this part and this number. Mirrors backend/app/ordering/reasons.py.
    reasons: {
      sellsPerWeek: (n: string) => `Sells about ${n} a week`,
      sellsPerMonth: (n: string) => `Sells about ${n} a month`,
      sellsLessThanMonthly: "Sells less than 1 a month",
      slowOutOfStock: (sold: string, quantity: string) =>
        `Out of stock, sold ${sold} in the last 90 days, no sale in 4 weeks: order ${quantity} to have it on the shelf.`,
      slowSkip: "No sale in 4 weeks: not ordered.",
      forecast: (w: {
        rate: string;
        deliveryDays: string;
        onHand: string;
        onOrder: string | null;
        quantity: string;
        packSize: string | null;
        days: string;
        cushion: string;
      }) =>
        `${w.rate}, supplier takes ${w.deliveryDays} days, ${w.onHand} left${w.onOrder ? `, ${w.onOrder} already ordered` : ""}: ` +
        `order ${w.quantity}${w.packSize ? ` (packs of ${w.packSize})` : ""} to cover the next ${w.days} days with a safety cushion of ${w.cushion}.`,
      cutByBudget: "Cut to stay within the budget.",
    },
    settings: {
      title: "How careful should orders be?",
      levels: {
        "0.8": "Save money",
        "0.9": "Balanced",
        "0.95": "Never run out",
      } as Record<string, string>,
      help: {
        "0.8": "Orders a smaller safety cushion. Cheaper, but a few parts may run out between orders.",
        "0.9": "A safety cushion that runs out about 1 time in 10. Recommended for most shops.",
        "0.95": "A bigger safety cushion, so parts almost never run out. Costs more to hold in stock.",
      } as Record<string, string>,
      saved: "Saved.",
    },
  },
  purchaseOrders: {
    subtitle: "One order per supplier, from parts a manager approved.",
    emptyTitle: "No purchase orders yet.",
    emptyText: "Approve lines in “What to order” to create one.",
    columns: {
      orderNumber: "Order",
      supplier: "Supplier",
      status: "Status",
      lines: "Lines",
      total: "Total",
      date: "Date",
    },
    statuses: { draft: "Draft", sent: "Sent", received: "Received" },
    markSent: "Mark as sent",
    sent: "Marked as sent.",
    receive: "Receive",
    receiveTitle: (orderNumber: string) => `Receive ${orderNumber}`,
    receiveHelp: "How many of each part arrived? Leave the rest for 0 and receive them later.",
    receiveSave: "Save what arrived",
    received: "Stock updated.",
    receivedQuantity: "Received so far",
    quantityOutOfRange: (max: string) => `Enter a number from 0 to ${max}`,
    downloadPdf: "Download PDF",
    print: {
      orderNumber: "Purchase order",
      date: "Date",
      supplier: "Supplier",
      part: "Part",
      sku: "SKU",
      branch: "Branch",
      quantity: "Quantity",
      unitCost: "Unit cost",
      total: "Total",
    },
  },
  part: {
    stockPerBranch: "Stock per branch",
    total: "Total",
    prices: "Prices",
    unitCost: "Unit cost",
    salePrice: "Sale price",
    minStock: "Minimum stock",
    minStockHelp: "At or below this number, the part shows as Low stock.",
    supplier: "Supplier",
    noSupplier: "No supplier",
    deliveryDays: (days: number) => `Delivers in ${days} days`,
    lastSales: "Last 10 sales",
    noSales: "No sales recorded yet.",
    sold: (quantity: string) => `${quantity} sold`,
    details: "Details",
    sku: "SKU",
    name: "Name",
    brand: "Brand",
    category: "Category",
    oem: "OEM reference",
    active: "Part is active",
    activeHelp: "Inactive parts are left out of the counts.",
    edit: "Edit part",
    editTitle: (name: string) => `Edit ${name}`,
    save: "Save changes",
    saved: "Part saved.",
    moneyHelp: (currency: string) => `In ${currency}, e.g. 12,50`,
    moneyError: "Enter an amount, e.g. 12,50",
    quantityError: "Enter a whole number, 0 or more",
    forecast: {
      title: "Expected to sell",
      tabs: { "7": "7 days", "30": "30 days", "60": "60 days" },
      about: (quantity: string) => `About ${quantity}`,
      likelyBetween: (low: string, high: string) => `Likely between ${low} and ${high}`,
      showDetails: "Show details",
      hideDetails: "Hide details",
      methodLabels: {
        four_week_average: "Average of the last 4 weeks",
        last_week: "Same as last week, repeated",
        exponential_smoothing: "Follows your most recent sales",
        croston: "Method for slow sellers",
        sba: "Method for slow sellers",
        tsb: "Method for slow sellers",
        boosting: "Learned from all your parts",
      } as Record<string, string>,
      beatBaseline: (pct: string) => `On this part's own past, this was ${pct}% closer than a simple average.`,
      noBeatBaseline: "A simple average worked as well here, so we use it.",
      notEnoughHistory: "Not enough sales yet to forecast this part. Needs about 8 weeks of sales.",
      chartSold: "Sold",
      chartForecast: "Forecast",
      noSalesYet: "No sales recorded yet, so there is nothing to chart.",
    },
    equivalents: {
      title: "Same part, other brands",
      none: "No equivalent parts found yet.",
      inStock: "In stock",
      outOfStock: "Out of stock",
      reasonOem: "Same OEM number",
      reasonManual: (name: string) => `Added by ${name}`,
      reasonSupplierFile: "From supplier file",
      link: "Link a part",
      linkTitle: "Link an equivalent part",
      linkHelp: "Search for the same part, sold under another brand.",
      searchPlaceholder: "Search by name, SKU or OEM reference",
      searching: "Searching…",
      noResults: "No parts found.",
      linked: (name: string) => `Linked to ${name}.`,
      removeTitle: "Remove this link?",
      removeText: "The two parts will no longer show as the same part.",
      removed: "Link removed.",
    },
  },
  importFile: {
    subtitle: "Bring your parts, stock and sales in from Excel or CSV.",
    steps: { upload: "Upload", match: "Match columns", check: "Check", save: "Save" },
    kindLabel: "What is in the file?",
    kinds: {
      parts: { title: "Parts and stock", text: "Your parts list with prices and how many you have." },
      sales: { title: "Sales history", text: "Past sales: date, part and quantity. Forecasts will learn from it." },
      equivalents: {
        title: "Equivalent parts",
        text: "A supplier's cross-reference file: which of your parts are the same part under another brand.",
      },
    },
    fileLabel: "File",
    fileHelp: "Excel (.xlsx) or CSV, up to 10 MB.",
    chooseFile: "Choose a file",
    changeFile: "Choose another file",
    fileTooBig: "The file is larger than 10 MB. Split it into smaller files.",
    wrongType: "Use an Excel file (.xlsx) or a CSV file (.csv).",
    noFile: "Choose a file first.",
    readFile: "Read the file",
    matchText: (rows: string) => `Tell us what each column contains. ${rows} rows found.`,
    remembered: "We filled this in from your last import. Check it before going on.",
    firstRows: "First rows",
    columnField: (header: string) => `What is in “${header}”?`,
    ignore: "Ignore this column",
    required: "required",
    stillToMatch: (labels: string) => `Still to match: ${labels}.`,
    chosenTwice: (label: string) => `${label} is chosen for two columns.`,
    checkFile: "Check the file",
    fieldNames: {
      parts: {
        sku: "SKU",
        name: "Name",
        brand: "Brand",
        category: "Category",
        oem_reference: "OEM reference",
        unit_cost: "Unit cost",
        sale_price: "Sale price",
        min_stock: "Minimum stock",
        pack_size: "Pack size",
        quantity: "Quantity in stock",
        branch: "Branch",
        supplier: "Supplier",
      },
      sales: {
        date: "Date",
        sku: "SKU",
        quantity: "Quantity sold",
        unit_price: "Unit price",
        branch: "Branch",
      },
      equivalents: {
        our_code: "Our code",
        equivalent_code: "Equivalent code",
      },
    } as Record<"parts" | "sales" | "equivalents", Record<string, string>>,
    nothingSaved: "Nothing is saved yet. This is what will happen:",
    counts: {
      new_parts: (n: string) => `${n} new parts`,
      updated_parts: (n: string) => `${n} parts updated`,
      unchanged_parts: (n: string) => `${n} parts unchanged`,
      new_sales: (n: string) => `${n} new sales lines`,
      already_imported: (n: string) => `${n} sales lines already imported (skipped)`,
      problem_rows: (n: string) => `${n} rows with problems (skipped)`,
      new_equivalents: (n: string) => `${n} new equivalent parts linked`,
      already_linked: (n: string) => `${n} already linked (skipped)`,
    } as Record<string, (n: string) => string>,
    newBranches: (names: string) => `New branches: ${names}`,
    newSuppliers: (count: string, names: string) => `${count} new suppliers: ${names}`,
    problemsTitle: "Rows with problems",
    problemsText: "These rows will be skipped. Fix them in your file and import it again if you need them.",
    row: "Row",
    problem: "Problem",
    moreProblems: (count: string) => `…and ${count} more rows with problems.`,
    save: "Save import",
    nothingToSave: "There is nothing new to save in this file.",
    doneTitle: "Import saved",
    goToStock: "Go to stock",
    importAnother: "Import another file",
  },
  roles: {
    owner: "Owner",
    manager: "Manager",
    staff: "Staff",
  },
  fields: {
    shopName: "Shop name",
    yourName: "Your name",
    name: "Name",
    email: "Email",
    password: "Password",
    temporaryPassword: "Temporary password",
    currentPassword: "Current password",
    newPassword: "New password",
    repeatNewPassword: "Type the new password again",
    role: "Role",
  },
  validation: {
    required: "Fill this in.",
    email: "Enter a valid email address, for example name@shop.ma.",
    passwordLength: "Use at least 10 characters for the password.",
    passwordsDiffer: "The two passwords don't match.",
  },
  setup: {
    title: "Set up your shop",
    subtitle: "You will be the owner. You can add your team after this.",
    shopNameHelp: "As your customers know it, e.g. Atlas Auto Parts.",
    passwordHelp: "At least 10 characters.",
    submit: "Create shop",
  },
  login: {
    title: "Log in",
    subtitle: "Welcome back to AutoStock AI.",
    submit: "Log in",
  },
  nav: {
    home: "Home",
    ask: "Ask",
    alerts: "Alerts",
    activity: "Activity",
    team: "Team",
    settings: "Settings",
    stock: "Stock",
    orders: "What to order",
    importFile: "Import",
    changePassword: "Change password",
    notFound: "Page not found",
    mainMenu: "Main menu",
    openMenu: "Open menu",
    skipToContent: "Skip to content",
  },
  account: {
    menuLabel: (name: string) => `Account menu for ${name}`,
    language: "Language",
    changePassword: "Change password",
    logOut: "Log out",
  },
  home: {
    greeting: (partOfDay: "morning" | "afternoon" | "evening", name: string) => `Good ${partOfDay}, ${name}`,
    // "18 stock problems to check · 222 parts to order · 1 late delivery", each part left out
    // when its count is 0. "Worth a look" doesn't count: it's informational, nothing to check.
    needsYouToday: ({
      stockProblems,
      partsToOrder,
      lateDeliveries,
    }: {
      stockProblems: number;
      partsToOrder: number;
      lateDeliveries: number;
    }) => {
      const segments = [
        stockProblems > 0 && (stockProblems === 1 ? "1 stock problem to check" : `${stockProblems} stock problems to check`),
        partsToOrder > 0 && (partsToOrder === 1 ? "1 part to order" : `${partsToOrder} parts to order`),
        lateDeliveries > 0 && (lateDeliveries === 1 ? "1 late delivery" : `${lateDeliveries} late deliveries`),
      ].filter((segment): segment is string => Boolean(segment));
      return segments.length === 0 ? "All good today. Nothing needs you." : segments.join(" · ");
    },
    needsAction: {
      title: "Needs action",
      empty: "Nothing needs action right now.",
    },
    worthALook: {
      title: "Worth a look",
      empty: "Nothing unusual in sales this week.",
    },
    seeAllAlerts: "See all alerts",
    lookedAtIt: "Looked at it",
    notAProblem: "Not a problem",
    lookedAtItDone: "Marked as looked at.",
    notAProblemDone: "Marked as not a problem.",
    toOrder: {
      title: "To order",
      summary: (lines: string, cost: string) => `${lines} lines to order, ${cost}`,
      linesOnly: (lines: string) => `${lines} lines to order`,
      empty: "Nothing to order right now.",
      button: "Go to What to order",
    },
    lateDeliveries: {
      title: "Late deliveries",
      empty: "Nothing is late.",
      daysLate: (days: number) => (days === 1 ? "1 day late" : `${days} days late`),
      sentOn: (date: string) => `Sent ${date}`,
    },
    weeklySales: {
      title: "This week's sales",
      normalWeek: (normal: string) => `Normal week: about ${normal}`,
      topParts: "Top 5 parts sold this week",
      noSalesYet: "No sales recorded yet.",
    },
  },
  activity: {
    subtitle: "Everything that changed in your shop, newest first.",
    person: "Person",
    allPeople: "Everyone",
    kind: "Type of change",
    kinds: {
      all: "All changes",
      team: "Team changes",
      passwords: "Passwords",
      logins: "Logins",
      settings: "Shop settings",
      stock: "Stock changes",
    },
    nothingYet: "Nothing has happened yet.",
    nothingMatches: "No activity matches these filters.",
    someone: "Someone",
    shop: "the shop",
    sentences: {
      shopCreated: (actor: string, shop: string) => `${actor} created the shop ${shop}.`,
      synonymsChanged: (actor: string) => `${actor} changed the search words.`,
      shopRenamed: (actor: string, from: string, to: string) => `${actor} renamed the shop from ${from} to ${to}.`,
      currencyChanged: (actor: string, from: string, to: string) =>
        `${actor} changed the currency from ${from} to ${to}.`,
      personAdded: (actor: string, target: string, role: string) => `${actor} added ${target} as ${role}.`,
      joinedAsFounder: (actor: string, role: string) => `${actor} set up the shop as ${role}.`,
      ownRoleChanged: (actor: string, from: string, to: string) =>
        `${actor} changed their own role from ${from} to ${to}.`,
      deactivatedSelf: (actor: string) => `${actor} deactivated their own account.`,
      roleChanged: (actor: string, target: string, from: string, to: string) =>
        `${actor} changed ${target}'s role from ${from} to ${to}.`,
      deactivated: (actor: string, target: string) => `${actor} deactivated ${target}.`,
      reactivated: (actor: string, target: string) => `${actor} reactivated ${target}.`,
      passwordChanged: (actor: string) => `${actor} changed their password.`,
      passwordReset: (actor: string, target: string) => `${actor} reset ${target}'s password.`,
      loggedIn: (actor: string) => `${actor} logged in.`,
      importedParts: (actor: string, file: string, created: string, updated: string) =>
        `${actor} imported ${file}: ${created} new parts, ${updated} updated.`,
      importedSales: (actor: string, file: string, lines: string) => `${actor} imported ${file}: ${lines} sales lines.`,
      importedEquivalents: (actor: string, file: string, linked: string) =>
        `${actor} imported ${file}: ${linked} new equivalent parts linked.`,
      partEdited: (actor: string, part: string, sku: string) => `${actor} edited ${part} (${sku}).`,
      partsLinked: (actor: string, part: string, other: string) => `${actor} linked ${part} to ${other}.`,
      partsUnlinked: (actor: string, part: string, other: string) => `${actor} removed the link between ${part} and ${other}.`,
      branchRenamed: (actor: string, from: string, to: string) => `${actor} renamed the branch from ${from} to ${to}.`,
      branchMerged: (actor: string, from: string, into: string) => `${actor} merged branch ${from} into ${into}.`,
      branchRemoved: (actor: string, name: string) => `${actor} removed branch ${name}.`,
      supplierMerged: (actor: string, from: string, into: string) => `${actor} merged supplier ${from} into ${into}.`,
      supplierRemoved: (actor: string, name: string) => `${actor} removed supplier ${name}.`,
      orderCareChanged: (actor: string, level: string) => `${actor} changed how careful orders should be to "${level}".`,
      languageChanged: (actor: string, language: string) => `${actor} changed the shop's language to ${language}.`,
      forecastRequested: (actor: string) => `${actor} asked for forecasts to be recalculated.`,
      suggestionsCreated: (actor: string, lines: string, cut: string) =>
        `${actor} worked out what to order: ${lines} lines to decide on, ${cut} cut by the budget.`,
      suggestionsCreatedEmpty: (actor: string) => `${actor} asked for order suggestions, but there is no sales history yet.`,
      orderApproved: (actor: string, quantity: string, part: string, branch: string) =>
        `${actor} approved ordering ${quantity} of ${part} for ${branch}.`,
      orderRejected: (actor: string, part: string, branch: string) => `${actor} rejected ordering ${part} for ${branch}.`,
      purchaseOrderCreated: (actor: string, orderNumber: string, supplier: string) =>
        `${actor} created purchase order ${orderNumber} for ${supplier}.`,
      purchaseOrderSent: (actor: string, orderNumber: string, supplier: string) =>
        `${actor} marked purchase order ${orderNumber} to ${supplier} as sent.`,
      purchaseOrderReceived: (actor: string, orderNumber: string, supplier: string) =>
        `${actor} received purchase order ${orderNumber} from ${supplier} in full.`,
      stockReceived: (actor: string, quantity: string, part: string, branch: string, orderNumber: string) =>
        `${actor} received ${quantity} of ${part} at ${branch} (${orderNumber}).`,
      alertLookedAt: (actor: string, part: string, branch: string) => `${actor} looked at the alert on ${part} at ${branch}.`,
      alertNotAProblem: (actor: string, part: string, branch: string) =>
        `${actor} marked the alert on ${part} at ${branch} as not a problem.`,
      otherChange: (actor: string) => `${actor} made a change.`,
    },
  },
  time: {
    justNow: "just now",
  },
  settings: {
    subtitle: "Your shop's name, currency, branches, suppliers and search words.",
    cardTitle: "Shop",
    shopName: "Shop name",
    shopNameHelp: "Shown at the top of every page.",
    currency: "Currency",
    currencyHelp: "Prices and costs are shown in this currency.",
    currencies: { MAD: "MAD · Moroccan dirham", EUR: "EUR · Euro", USD: "USD · US dollar" },
    language: "Language",
    languageHelp: "Everyone sees the app in this language, unless they choose their own in their account menu.",
    saved: "Settings saved.",
    branches: {
      title: "Branches",
      description: "Where stock is kept. Rename one, merge two that mean the same place, or remove one you added by mistake.",
      usedNote: "Has stock or sales, merge it instead",
    },
    suppliers: {
      title: "Suppliers",
      description: "Who you order parts from. Rename one, merge a duplicate into another, or remove one no part uses.",
      usedNote: "Used by some parts, merge it instead",
    },
    synonyms: {
      title: "Search words",
      description:
        "Words that mean the same part. Searching one finds the others, so “brake pads”, “plaquettes de frein” and “فحمات الفرامل” find the same parts.",
      field: "Words that mean the same",
      help: "One line per part type. Separate the words with commas.",
      saved: "Search words saved.",
    },
    entities: {
      rename: "Rename",
      nameField: "Name",
      renameTitle: (name: string) => `Rename ${name}`,
      renamed: (from: string, to: string) => `${from} is now called ${to}.`,
      merge: "Merge",
      mergeTitle: (name: string) => `Merge ${name}`,
      mergeText: (name: string) => `Everything under ${name} moves to the one you choose, and ${name} is removed.`,
      mergeInto: "Merge into",
      merged: (from: string, into: string) => `${from} was merged into ${into}.`,
      removeTitle: (name: string) => `Remove ${name}?`,
      removeText: "This can't be undone.",
      removed: (name: string) => `${name} was removed.`,
    },
  },
  changePassword: {
    title: "Change password",
    subtitle: "You stay logged in here. Other devices where you are logged in are logged out.",
    forcedTitle: "Choose your password",
    forcedSubtitle: "Your shop owner gave you a temporary password. Choose your own to continue.",
    newPasswordHelp: "At least 10 characters.",
    submit: "Save new password",
    done: "Your password was changed.",
  },
  team: {
    subtitle: "People who can use AutoStock AI in your shop.",
    addPerson: "Add person",
    columns: { person: "Person", role: "Role", status: "Status", lastLogin: "Last login", access: "Access" },
    active: "Active",
    deactivated: "Deactivated",
    needsNewPassword: "Must choose a password",
    deactivate: "Deactivate",
    reactivate: "Reactivate",
    changeRoleLabel: (name: string) => `Role of ${name}`,
    roleChanged: (name: string, role: string) => `${name} is now ${role}.`,
    deactivateTitle: (name: string) => `Deactivate ${name}?`,
    deactivateText: "They are logged out right away and can't log in until you reactivate them.",
    nowDeactivated: (name: string) => `${name} can no longer log in.`,
    reactivated: (name: string) => `${name} can log in again.`,
    addTitle: "Add a person",
    addText: "They log in with this email and the temporary password you choose.",
    temporaryPasswordHelp: "At least 10 characters. Give it to them in person.",
    added: (name: string) => `${name} was added. Give them their email and temporary password.`,
    resetPassword: "Reset password",
    resetTitle: (name: string) => `Reset the password of ${name}?`,
    resetText: "They are logged out everywhere. They log in with the temporary password, then choose their own.",
    resetDone: (name: string) => `New temporary password set. Give it to ${name} in person.`,
  },
  alertsPage: {
    subtitle: "Everything unusual that needs a look, newest first.",
    group: "Group",
    allGroups: "All alerts",
    groups: { needs_action: "Needs action", worth_a_look: "Worth a look" },
    status: "Status",
    allStatuses: "All statuses",
    statuses: { open: "Open", looked_at: "Looked at", not_a_problem: "Not a problem" },
    nothingYet: "No alerts yet.",
    nothingMatches: "No alerts match these filters.",
    markedBy: (name: string) => `Marked by ${name}`,
  },
  // Built from each alert's own numbers. Mirrors backend/app/alerts/sales_rules.py and stock_rules.py.
  alerts: {
    kinds: {
      sales_spike: "Sales much higher than usual",
      sales_drop: "Sales much lower than usual",
      sold_at_zero: "Sold while stock showed 0",
      stock_frozen: "Stock count not moving",
      negative_stock: "Stock below zero",
    } as Record<string, string>,
    sales: (sold: string, day: string, low: string, high: string) =>
      `Sold ${sold} in the 7 days to ${day}, usually ${low} to ${high}.`,
    negativeStock: (quantity: string, day: string) =>
      `Stock shows ${quantity} since ${day}: below zero is impossible, so the count is wrong.`,
    soldAtZero: (pieces: string, days: string, day: string) => `Sold ${pieces} on ${days} since ${day} while stock showed 0.`,
    stockFrozen: (quantity: string, day: string, pieces: string) =>
      `Stock stuck at ${quantity} since ${day} while ${pieces} were sold.`,
    money: {
      sales_spike: (money: string) => `About ${money} of sales above usual.`,
      sales_drop: (money: string) => `About ${money} of sales below usual.`,
      sold_at_zero: (money: string) => `About ${money} of stock not counted.`,
      stock_frozen: (money: string) => `About ${money} of stock may be missing.`,
      negative_stock: (money: string) => `About ${money} of stock to recount.`,
    } as Record<string, (money: string) => string>,
  },
  ask: {
    subtitle: "Ask a question about your shop, in your own words.",
    inputLabel: "Ask a question about your shop",
    inputPlaceholder: "e.g. What's running out?",
    submit: "Ask",
    thinking: "Thinking…",
    emptyTitle: "Ask anything about your shop",
    emptyDescription: "Try one of the examples above, or type your own question.",
    asked: (question: string) => `You asked “${question}”`,
    tryInstead: "Try one of these instead:",
    didYouMean: "Did you mean:",
    partChip: (part: string) => `Part: ${part}`,
    examples: [
      "What are our best sellers this month?",
      "What's running out?",
      "Stock of brake pads in Rabat",
      "What should I order?",
      "Any open alerts?",
      "Which parts are dead stock?",
    ],
    types: {
      sales_of: "Sales",
      best_sellers: "Best sellers",
      running_out: "Running out",
      what_to_order: "What to order",
      stock_of_part: "Stock",
      dead_stock: "Dead stock",
      open_alerts: "Open alerts",
      late_deliveries: "Late deliveries",
      forecast_of_part: "Forecast",
      sales_vs_last: "Sales vs. last period",
    },
    filters: {
      category: "Category",
      allCategories: "Any category",
      branch: "Branch",
      allBranches: "Any branch",
      period: "Period",
      allPeriods: "Any time",
    },
    periods: {
      today: "Today",
      yesterday: "Yesterday",
      this_week: "This week",
      last_week: "Last week",
      this_month: "This month",
      last_month: "Last month",
      this_year: "This year",
    },
    relatedScreen: {
      stock: "Open Stock",
      orders: "Open What to order",
      alerts: "Open Alerts",
    },
    bestGuess: "Best guess.",
    aiOff: "AI is off: questions are read with simple keyword rules.",
    understood: (heading: string) => `I understood: ${heading}`,
    // "Sales of brake pads": the heading of the "I understood" line. Mirrors backend/app/ask/understood_line.py.
    headings: {
      sales_of: (subject: string | null) => (subject ? `Sales of ${subject}` : "Sales"),
      best_sellers: (subject: string | null) => (subject ? `Best sellers in ${subject}` : "Best sellers"),
      running_out: (subject: string | null) => (subject ? `Running out soon in ${subject}` : "Running out soon"),
      what_to_order: (subject: string | null) => (subject ? `What to order in ${subject}` : "What to order"),
      stock_of_part: (subject: string | null) => (subject ? `Stock of ${subject}` : "Stock"),
      dead_stock: (subject: string | null) => (subject ? `Dead stock in ${subject}` : "Dead stock"),
      open_alerts: (subject: string | null) => (subject ? `Open alerts for ${subject}` : "Open alerts"),
      late_deliveries: () => "Late deliveries",
      forecast_of_part: (subject: string | null) =>
        subject ? `Forecast of ${subject} for the next 30 days` : "Forecast for the next 30 days",
      sales_vs_last: (subject: string | null) =>
        subject ? `Sales of ${subject} compared with the period before` : "Sales compared with the period before",
    } as Record<string, (subject: string | null) => string>,
    categorySubject: (category: string) => `${category} (category)`,
    periodWords: {
      today: "today",
      yesterday: "yesterday",
      this_week: "this week",
      last_week: "last week",
      this_month: "this month",
      last_month: "last month",
      this_year: "this year",
      last_30_days: "the last 30 days",
    } as Record<string, string>,
    // What an answer is about, inside a sentence.
    subjects: {
      part: (name: string, count: string | null) => (count ? `${name} (${count} parts)` : name),
      matching: (words: string, count: string) => `parts matching “${words}” (${count} parts)`,
      category: (name: string) => `the ${name} category`,
      all: "all parts",
    },
    // One sentence per answer key. Mirrors the English sentences in backend/app/ask.
    answers: {
      not_sure: (w: AnswerWords) => `I'm not sure what you mean${w.words ? ` by “${w.words}”` : ""}. Did you mean one of these?`,
      cannot_answer: () => "I can't answer that yet.",
      part_not_found: (w: AnswerWords) => `I couldn't find a part matching “${w.part}”. Try its name or part number.`,
      which_part_stock: () => "Which part? For example: “how many oil filters in stock”.",
      which_part_forecast: () => "Which part? For example: “how many brake pads will we sell”.",
      sales_of: (w: AnswerWords) =>
        `${w.Subject}: ${w.pieces} sold${inBranch(w.branch)} ${w.period} (${w.range})${w.money ? `, worth ${w.money}` : ""}.`,
      best_sellers_none: (w: AnswerWords) => `No sales for ${w.subject}${inBranch(w.branch)} ${w.period} (${w.range}).`,
      best_sellers: (w: AnswerWords) =>
        `Best seller for ${w.subject}${inBranch(w.branch)} ${w.period} (${w.range}): ${w.name} (${w.sku}), ${w.pieces}.`,
      sales_vs_last: (w: AnswerWords) =>
        `${w.Subject}${inBranch(w.branch)}, ${w.period} (${w.range}): ${w.pieces}, ` +
        (w.percent === null
          ? "with no sales in the period before."
          : `${w.percent === 0 ? "the same as" : `${w.percent > 0 ? "up" : "down"} ${Math.abs(w.percent)}% on`} ${w.beforeRange} (${w.beforePieces}).`),
      stock_of_part: (w: AnswerWords) => `${w.Subject}: ${w.pieces} in stock${inBranch(w.branch)}.`,
      running_out_none: (w: AnswerWords) =>
        `Nothing in ${w.subject} is expected to run out${inBranch(w.branch)} within ${w.days} days.`,
      running_out: (w: AnswerWords) =>
        `${w.shownCount} ${w.count === 1 ? "part is" : "parts are"} expected to run out${inBranch(w.branch)} within ${w.days} days (${w.subject}). ` +
        `First: ${w.name} (${w.sku}), ${w.pieces} left, about ${w.daysLeft} days.`,
      dead_stock_none: (w: AnswerWords) => `No dead stock in ${w.subject}${inBranch(w.branch)} (no sale in ${w.days} days).`,
      dead_stock: (w: AnswerWords) =>
        `${w.shownCount} ${w.count === 1 ? "part has" : "parts have"} stock but no sale in ${w.days} days (${w.subject}${inBranch(w.branch)}): ` +
        `${w.pieces} on the shelf${w.money ? `, costing ${w.money}` : ""}.`,
      forecast_none: (w: AnswerWords) => `No forecast yet for ${w.subject}. Forecasts are made after sales are imported.`,
      forecast: (w: AnswerWords) =>
        `${w.Subject}${inBranch(w.branch)}: about ${w.pieces} expected over the next ${w.days} days ` +
        `(likely between ${w.low} and ${w.high}), from sales up to ${w.madeFrom}.`,
      what_to_order_no_run: () => "There is no order suggestion yet. A manager can make one on the Orders page.",
      what_to_order_none: (w: AnswerWords) =>
        `Nothing left to order for ${w.subject}${inBranch(w.branch)} (latest suggestion, ${w.madeOn}).`,
      what_to_order: (w: AnswerWords) =>
        `To order for ${w.subject}${inBranch(w.branch)}: ${w.shownCount} ${w.count === 1 ? "line" : "lines"}, ` +
        `${w.pieces}${w.money ? `, costing ${w.money}` : ""} (latest suggestion, ${w.madeOn}).`,
      open_alerts_none: (w: AnswerWords) => `No open alerts for ${w.subject}${inBranch(w.branch)}.`,
      open_alerts: (w: AnswerWords) =>
        `${w.shownCount} open ${w.count === 1 ? "alert" : "alerts"} for ${w.subject}${inBranch(w.branch)}. ` +
        `Newest: ${w.part} in ${w.alertBranch}: ${w.alert}`,
      late_deliveries_none: () => "No supplier delivery is late.",
      late_deliveries: (w: AnswerWords) =>
        `${w.shownCount} ${w.count === 1 ? "delivery is" : "deliveries are"} late. Most late: ${w.orderNumber} from ${w.supplier}, ${w.days} days.`,
    } as Record<string, (w: AnswerWords) => string>,
    // Labels of the real numbers under an answer.
    numberLabels: {
      pieces_sold: "Pieces sold",
      sales_value: "Sales value",
      from: "From",
      to: "To",
      pieces_now: "Pieces sold, this period",
      pieces_before: "Pieces sold, period before",
      value_now: "Sales value, this period",
      value_before: "Sales value, period before",
      this_period: "This period",
      period_before: "Period before",
      parts_running_out: "Parts running out",
      dead_parts: "Dead stock parts",
      pieces_on_shelf: "Pieces on the shelf",
      value_at_cost: "Value at cost",
      expected_next_30_days: "Expected, next 30 days",
      likely_at_least: "Likely at least",
      likely_at_most: "Likely at most",
      made_from_sales_up_to: "Made from sales up to",
      lines_to_order: "Lines to order",
      pieces_to_order: "Pieces to order",
      total_cost: "Total cost",
      open_alerts: "Open alerts",
      late_deliveries: "Late deliveries",
    } as Record<string, string>,
    numberLabelsAbout: {
      days_left: (about: string) => `${about}, days left`,
      days_late: (about: string) => `${about}, days late`,
    } as Record<string, (about: string) => string>,
    homeBox: {
      inputLabel: "Ask your shop",
      placeholder: "Ask your shop…",
      submit: "Ask",
    },
  },
  notFound: {
    title: "Page not found",
    description: "The link may be old or mistyped.",
  },
  // The server's messages are written in English, so English needs no table. See translateServerMessage.
  serverMessages: {
    fixed: {} as Record<string, string>,
    patterns: {} as Record<string, (...parts: string[]) => string>,
  },
};

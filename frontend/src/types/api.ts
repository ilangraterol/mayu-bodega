/**
 * Domain types. These mirror the DRF serializers in `backend/`; the backend is
 * the single source of truth for the shapes.
 *
 * Money and quantities arrive as strings (the API never serialises money as a
 * float). Use `parseMoney` / `formatMoney` from `lib/money` before doing
 * arithmetic or display.
 */

export const CURRENCY_USD = 'USD'
export const CURRENCY_VES = 'VES'
export type Currency = typeof CURRENCY_USD | typeof CURRENCY_VES

export const ROLES = ['ADMIN', 'GERENTE', 'ALMACENERO', 'CAJERO'] as const
export type Role = (typeof ROLES)[number]

export const UNIT_OF_MEASURE = [
  'UNIDAD',
  'PAQUETE',
  'BULTO',
  'CAJA',
  'LIBRA',
  'KILO',
  'LITRO',
  'UNIDAD_FISICA',
] as const
export type UnitOfMeasure = (typeof UNIT_OF_MEASURE)[number]

export interface User {
  id: number
  username: string
  first_name: string
  last_name: string
  full_name: string
  is_active: boolean
  roles: Role[]
}

export interface LoginResponse {
  token: string
  user: User
}

export interface StoreConfig {
  store_name: string
  allow_zero_stock_sale: boolean
  default_surcharge_percentage: string
  updated_at: string
}

export interface ProductImage {
  id: number
  product: number
  url: string
  thumbnail_url: string
  width: number
  height: number
  size_bytes: number
  is_primary: boolean
  sort_order: number
  created_at: string
}

/**
 * Where a line's surcharge came from, in precedence order:
 * `PRODUCT` (the article's own value) > `CATEGORY` > `STORE` (global default).
 * `MANUAL` means the cashier changed it for this line at the till.
 */
export const SURCHARGE_SOURCE = {
  MANUAL: 'MANUAL',
  PRODUCT: 'PRODUCT',
  CATEGORY: 'CATEGORY',
  STORE: 'STORE',
} as const
export type SurchargeSource = (typeof SURCHARGE_SOURCE)[keyof typeof SURCHARGE_SOURCE]

export interface Category {
  id: number
  code: string
  name: string
  /** `null` means "inherit", so the store default still applies. */
  surcharge_percentage: string | null
  /** Pre-formatted for the UI; `"Heredado"` when the category defines none. */
  surcharge_percentage_display: string
  is_active: boolean
  product_count: number
  created_at: string
  updated_at: string
}

export interface CategoryPayload {
  name: string
  /** An empty string is sent as `null`, which means "inherit". */
  surcharge_percentage?: string | null
  is_active?: boolean
}

export interface Product {
  id: number
  code: string
  barcode: string | null
  name: string
  brand: string
  category: number | null
  category_name: string | null
  /** The article's own surcharge, or `null` when it inherits. */
  surcharge_percentage: string | null
  /** Resolved article > category > store. Pre-fills the cart line. */
  effective_surcharge_percentage: string
  surcharge_source: SurchargeSource
  surcharge_source_display: string
  surcharge_presets: string[]
  unit_of_measure: UnitOfMeasure
  unit_of_measure_display: string
  units_per_package: number
  cost_usd: string
  price_usd: string
  /** Physical on-hand units. Never negative. */
  stock: string
  /** Units billed while the store allowed selling with zero stock. */
  pending_units: string
  /** `stock - pending_units`, the net position implied by the ledger. */
  net_units: string
  is_active: boolean
  notes: string
  primary_image_url: string
  can_sell_with_zero_stock: boolean
  images: ProductImage[]
  created_at: string
  updated_at: string
}

/** `ProductWriteSerializer`: the catalogue never accepts `stock`. */
export interface ProductPayload {
  barcode?: string | null
  name: string
  brand?: string
  category?: number | null
  /** An empty string is sent as `null`, which means "inherit". */
  surcharge_percentage?: string | null
  unit_of_measure: UnitOfMeasure
  units_per_package?: number | null
  cost_usd: string
  price_usd: string
  is_active?: boolean
  notes?: string
}

export interface ExchangeRate {
  id: number
  rate: string
  effective_date: string
  fetched_at: string
  source: 'BCV' | 'MANUAL'
  source_display: string
  is_active: boolean
  recorded_by: string | null
  notes: string
}

/** Countdown for the next allowed BCV read, so the UI never guesses. */
export interface BcvSyncStatus {
  last_fetched_at: string | null
  min_interval_seconds: number
  seconds_until_next_sync: number
  next_sync_available_at: string | null
  can_sync: boolean
}

export interface ManualRatePayload {
  rate: string
  effective_date: string
  notes: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Customer {
  id: number
  document_id: string | null
  name: string
  phone: string
  address: string
  notes: string
  is_active: boolean
  /** Pending credit across all open debts, already summed by the backend. */
  balance_usd: string
  open_debts: number
  created_at: string
  updated_at: string
}

export type CustomerPayload = Pick<
  Customer,
  'document_id' | 'name' | 'phone' | 'address' | 'notes' | 'is_active'
>

export interface CustomerStatement {
  customer: Customer
  debts: {
    id: number
    sale_code: string | null
    sale_date: string | null
    original_amount_usd: string
    balance_usd: string
    status: DebtStatus
    payments: {
      id: number
      amount: string
      currency: Currency
      amount_usd: string
      exchange_rate_applied: string
      method: PaymentMethod
      paid_at: string
    }[]
  }[]
}

export const SALE_TYPE = { PAID: 'PAID', CREDIT: 'CREDIT' } as const
export type SaleType = (typeof SALE_TYPE)[keyof typeof SALE_TYPE]

export const SALE_STATUS = { COMPLETED: 'COMPLETED', ANULLED: 'ANULLED' } as const
export type SaleStatus = (typeof SALE_STATUS)[keyof typeof SALE_STATUS]

export const PAYMENT_METHOD = {
  CASH_USD: 'CASH_USD',
  CASH_VES: 'CASH_VES',
  TRANSFER_USD: 'TRANSFER_USD',
  TRANSFER_VES: 'TRANSFER_VES',
  MIXED: 'MIXED',
  CARD: 'CARD',
} as const
export type PaymentMethod = (typeof PAYMENT_METHOD)[keyof typeof PAYMENT_METHOD]

export const DEBT_STATUS = { OPEN: 'OPEN', PAID: 'PAID', ANULLED: 'ANULLED' } as const
export type DebtStatus = (typeof DEBT_STATUS)[keyof typeof DEBT_STATUS]

export interface SaleItem {
  id: number
  product: number
  product_code: string
  product_name: string
  primary_image_url: string
  quantity: string
  unit_price_usd: string
  line_total_usd: string
  /** The percentage frozen into this line at the moment of the sale. */
  surcharge_percentage: string
  surcharge_usd: string
  surcharge_source: SurchargeSource
  surcharge_source_display: string
}

export interface Sale {
  id: number
  code: string
  sale_type: SaleType
  sale_type_display: string
  customer: number | null
  customer_name: string | null
  sale_date: string
  currency: Currency
  exchange_rate_applied: string
  surcharge_percentage: string
  subtotal_usd: string
  surcharge_usd: string
  total_usd: string
  total_ves: string
  paid_amount: string
  payment_method: PaymentMethod
  amount_due_usd: string
  status: SaleStatus
  status_display: string
  void_reason: string
  voided_at: string | null
  notes: string
  created_by: string
  created_at: string
  items: SaleItem[]
}

export interface SaleItemInput {
  product_id: number
  quantity: string
  unit_price_usd?: string
  /**
   * The percentage the cashier chose for this line. Omitted means "use the
   * catalogue", which is what an untouched cart sends.
   */
  surcharge_percentage?: string
}

export interface SalePayload {
  sale_type: SaleType
  customer_id?: number | null
  sale_date?: string | null
  currency: Currency
  paid_amount?: string | null
  payment_method: PaymentMethod
  notes?: string
  items: SaleItemInput[]
}

export interface QuoteLine {
  product_id: number
  product_code: string
  product_name: string
  quantity: string
  unit_price_usd: string
  stock: string
  line_total_usd: string
  /** The percentage this line would pay: the chosen one, or the inherited one. */
  surcharge_percentage: string
  surcharge_usd: string
  surcharge_source: SurchargeSource
  surcharge_source_display: string
  /** The line subtotal plus its own surcharge. */
  total_with_surcharge_usd: string
}

export interface Quote {
  subtotal_usd: string
  surcharge_usd: string
  total_usd: string
  total_ves: string
  exchange_rate_applied: string
  rate_effective_date: string
  /** Subtotal-weighted average of the per-line percentages. */
  surcharge_percentage: string
  allow_zero_stock_sale: boolean
  /** Quick-pick percentages offered by the till. */
  surcharge_presets: string[]
  lines: QuoteLine[]
}

export interface DebtPayment {
  id: number
  debt: number
  currency: Currency
  amount: string
  exchange_rate_applied: string
  amount_usd: string
  method: PaymentMethod
  paid_at: string
  is_voided: boolean
  voided_at: string | null
  void_reason: string
  notes: string
  recorded_by: string
  created_at: string
}

export interface CustomerDebt {
  id: number
  sale: number
  sale_code: string
  sale_date: string
  customer: number
  customer_name: string
  customer_document_id: string | null
  original_amount_usd: string
  paid_amount_usd: string
  balance_usd: string
  status: DebtStatus
  payments: DebtPayment[]
  created_at: string
  updated_at: string
}

export interface DebtPaymentPayload {
  amount: string
  currency: Currency
  method: PaymentMethod
  paid_at?: string | null
  notes?: string
}

/** `POST /debts/{id}/payments/` returns the payment plus the refreshed debt. */
export interface DebtPaymentCreated extends Omit<DebtPayment, 'debt'> {
  debt: CustomerDebt
}

export interface SalesSummary {
  date: string
  sales_count: number
  total_usd: string
  credit_sales_count: number
  open_debts_count: number
  pending_debt_usd: string
}

export const MOVEMENT_TYPE = { IN: 'IN', OUT: 'OUT' } as const
export type MovementType = (typeof MOVEMENT_TYPE)[keyof typeof MOVEMENT_TYPE]

export const EXIT_REASON = {
  MERMA: 'MERMA',
  CONSUMO_INTERNO: 'CONSUMO_INTERNO',
  PERDIDA: 'PERDIDA',
  DEVOLUCION: 'DEVOLUCION',
  DANO: 'DANO',
  VENCIMIENTO: 'VENCIMIENTO',
  OTRO: 'OTRO',
} as const
export type ExitReason = (typeof EXIT_REASON)[keyof typeof EXIT_REASON]

export interface StockMovement {
  id: number
  product: number
  product_code: string
  product_name: string
  movement_type: MovementType
  movement_type_display: string
  origin: string
  origin_display: string
  origin_id: number | null
  quantity: string
  unit_cost_usd: string | null
  unit_price_usd: string | null
  balance_after: string
  pending_after: string
  occurred_at: string
  notes: string
  created_by: string | null
  created_at: string
}

export interface EntryItemInput {
  product_id: number
  quantity: string
  unit_cost: string
}

export interface GoodsEntryItem {
  id: number
  product: number
  product_code: string
  product_name: string
  quantity: string
  unit_cost: string
  currency: Currency
  rate_applied: string | null
  unit_cost_usd: string
  line_total_usd: string
}

export interface GoodsEntry {
  id: number
  code: string
  supplier_name: string
  entry_date: string
  currency: Currency
  rate_applied: string | null
  total_usd: string
  notes: string
  is_cancelled: boolean
  cancelled_at: string | null
  created_by: string
  created_at: string
  items: GoodsEntryItem[]
}

export interface GoodsEntryPayload {
  supplier_name?: string
  entry_date: string
  currency: Currency
  rate_applied?: string | null
  notes?: string
  items: EntryItemInput[]
}

export interface ExitNoteItemInput {
  product_id: number
  quantity: string
}

export interface ExitNoteItem {
  id: number
  product: number
  product_code: string
  product_name: string
  quantity: string
  unit_cost_usd: string | null
}

export interface ExitNote {
  id: number
  code: string
  reason: ExitReason
  reason_display: string
  description: string
  exit_date: string
  total_units: string
  is_cancelled: boolean
  cancelled_at: string | null
  created_by: string
  created_at: string
  items: ExitNoteItem[]
}

export interface ExitNotePayload {
  reason: ExitReason
  description: string
  exit_date: string
  items: ExitNoteItemInput[]
}

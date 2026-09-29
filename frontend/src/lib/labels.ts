/** Spanish display labels for the API's enum values. */

import { EXIT_REASON, MOVEMENT_TYPE, PAYMENT_METHOD, SALE_TYPE, UNIT_OF_MEASURE } from '../types/api'
import type { ExitReason, MovementType, PaymentMethod, Role, SaleType, UnitOfMeasure } from '../types/api'

export const ROLE_LABELS: Record<Role, string> = {
  ADMIN: 'Administrador',
  GERENTE: 'Gerente',
  ALMACENERO: 'Almacenero',
  CAJERO: 'Cajero',
}

export const UNIT_LABELS: Record<UnitOfMeasure, string> = {
  UNIDAD: 'Unidad',
  PAQUETE: 'Paquete',
  BULTO: 'Bulto',
  CAJA: 'Caja',
  LIBRA: 'Libra',
  KILO: 'Kilo',
  LITRO: 'Litro',
  UNIDAD_FISICA: 'Unidad física',
}

export const UNIT_OPTIONS = (Object.keys(UNIT_LABELS) as UnitOfMeasure[]).map((value) => ({
  value,
  label: UNIT_LABELS[value],
}))

export const SALE_TYPE_LABELS: Record<SaleType, string> = {
  PAID: 'Pagada',
  CREDIT: 'Fiada',
}

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  CASH_USD: 'Efectivo USD',
  CASH_VES: 'Efectivo VES',
  TRANSFER_USD: 'Transferencia USD',
  TRANSFER_VES: 'Transferencia VES',
  MIXED: 'Mixto',
  CARD: 'Tarjeta',
}

export const PAYMENT_METHOD_OPTIONS = (
  Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]
).map((value) => ({ value, label: PAYMENT_METHOD_LABELS[value] }))

/** Methods that receive bolivars, so the UI can pair currency with method. */
export const VES_METHODS: PaymentMethod[] = ['CASH_VES', 'TRANSFER_VES']
export const USD_METHODS: PaymentMethod[] = ['CASH_USD', 'TRANSFER_USD', 'CARD', 'MIXED']

export const EXIT_REASON_LABELS: Record<ExitReason, string> = {
  MERMA: 'Merma',
  CONSUMO_INTERNO: 'Consumo interno',
  PERDIDA: 'Pérdida',
  DEVOLUCION: 'Devolución',
  DANO: 'Daño',
  VENCIMIENTO: 'Vencimiento',
  OTRO: 'Otro',
}

export const EXIT_REASON_OPTIONS = (Object.keys(EXIT_REASON_LABELS) as ExitReason[]).map(
  (value) => ({ value, label: EXIT_REASON_LABELS[value] }),
)

export const MOVEMENT_TYPE_LABELS: Record<MovementType, string> = {
  IN: 'Entrada',
  OUT: 'Salida',
}

export const ORIGIN_LABELS: Record<string, string> = {
  ENTRADA: 'Nota de entrada',
  VENTA: 'Venta',
  ANULACION_VENTA: 'Anulación de venta',
  NOTA_SALIDA: 'Nota de salida',
  ANULACION_SALIDA: 'Anulación de salida',
  AJUSTE: 'Ajuste',
}

export const SALE_TYPE_OPTIONS = (Object.keys(SALE_TYPE_LABELS) as SaleType[]).map((value) => ({
  value,
  label: SALE_TYPE_LABELS[value],
}))

export { MOVEMENT_TYPE, EXIT_REASON, PAYMENT_METHOD, SALE_TYPE, UNIT_OF_MEASURE }

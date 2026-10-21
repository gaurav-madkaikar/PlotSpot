// Accept only in-app destinations we intentionally offer after sign-in.
export function safeAccountReturn(value: string | null): string | null {
  if (value === '/collections' || value === '/collection') return '/collections'
  const match = value?.match(/^\/movies\/([1-9]\d{0,9})#(facts|quiz|discuss)$/)
  return match && Number(match[1]) <= 2147483647 ? value : null
}

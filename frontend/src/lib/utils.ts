import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function runtimeLabel(minutes: number | null) {
  if (minutes === null) return 'Runtime unavailable'
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

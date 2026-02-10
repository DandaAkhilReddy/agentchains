/**
 * Currency and number formatting utilities.
 * Supports INR (Indian) and USD (US) formatting.
 */

import type { CountryCode } from "../store/countryStore";

// ---------- INR (Indian Rupee) ----------

export function formatINR(amount: number): string {
  if (amount === 0) return "₹0";

  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);

  // Indian numbering: last 3 digits, then groups of 2
  const parts = absAmount.toFixed(2).split(".");
  const integerPart = parts[0];
  const decimalPart = parts[1];

  let result: string;
  if (integerPart.length <= 3) {
    result = integerPart;
  } else {
    const lastThree = integerPart.slice(-3);
    const rest = integerPart.slice(0, -3);
    const formattedRest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    result = `${formattedRest},${lastThree}`;
  }

  const formatted = decimalPart === "00" ? result : `${result}.${decimalPart}`;
  return `${isNegative ? "-" : ""}₹${formatted}`;
}

export function formatINRCompact(amount: number): string {
  const absAmount = Math.abs(amount);
  if (absAmount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (absAmount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (absAmount >= 1000) return `₹${(amount / 1000).toFixed(1)}K`;
  return formatINR(amount);
}

// ---------- USD (US Dollar) ----------

export function formatUSD(amount: number, decimals: number = 2): string {
  if (amount === 0) return "$0";

  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);

  const parts = absAmount.toFixed(decimals).split(".");
  const integerPart = parts[0];
  const decimalPart = parts[1];

  // Standard US grouping: groups of 3
  const formattedInt = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const allZeros = decimalPart && /^0+$/.test(decimalPart);
  const formatted = allZeros ? formattedInt : `${formattedInt}.${decimalPart}`;
  return `${isNegative ? "-" : ""}$${formatted}`;
}

export function formatUSDCompact(amount: number): string {
  const absAmount = Math.abs(amount);
  if (absAmount >= 1000000000) return `$${(amount / 1000000000).toFixed(1)}B`;
  if (absAmount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
  if (absAmount >= 1000) return `$${(amount / 1000).toFixed(1)}K`;
  return formatUSD(amount);
}

// ---------- Country-aware public API ----------

export function formatCurrency(amount: number, country: CountryCode = "IN"): string {
  return country === "US" ? formatUSD(amount) : formatINR(amount);
}

export function formatCurrencyCompact(amount: number, country: CountryCode = "IN"): string {
  return country === "US" ? formatUSDCompact(amount) : formatINRCompact(amount);
}

// ---------- Shared utilities ----------

export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatMonths(months: number): string {
  const years = Math.floor(months / 12);
  const remaining = months % 12;
  if (years === 0) return `${remaining} month${remaining !== 1 ? "s" : ""}`;
  if (remaining === 0) return `${years} year${years !== 1 ? "s" : ""}`;
  return `${years}y ${remaining}m`;
}

export function formatDate(date: string | Date, country: CountryCode = "IN"): string {
  const locale = country === "US" ? "en-US" : "en-IN";
  return new Date(date).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

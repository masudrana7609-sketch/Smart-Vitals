import { useEffect, useState } from "react";

// Recharts draws SVG with colour attributes, which cannot read CSS variables, so the chart colours are read
// from the stylesheet's tokens and re-read when the light/dark setting changes.
const NAMES = ["series-1", "series-2", "critical", "warning", "grid", "axis", "band", "limit", "surface", "text-2"] as const;
export type Tokens = Record<(typeof NAMES)[number], string>;

function read(): Tokens {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(NAMES.map((n) => [n, style.getPropertyValue(`--${n}`).trim() || "#888"])) as Tokens;
}

export function useTokens(): Tokens {
  const [tokens, setTokens] = useState(read);
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const update = () => setTokens(read());
    media?.addEventListener?.("change", update);
    return () => media?.removeEventListener?.("change", update);
  }, []);
  return tokens;
}

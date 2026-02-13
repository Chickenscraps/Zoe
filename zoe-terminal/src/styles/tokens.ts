/**
 * Design tokens as Tailwind class strings.
 * Usage: <h1 className={cn(typography.h1, "other-classes")} />
 *
 * Sakura SNES theme — headings use pixel font, body uses Inter.
 */

export const typography = {
  /** Pixel font heading — large */
  h1: "font-pixel text-sm uppercase tracking-[0.08em]",

  /** Pixel font heading — medium */
  h2: "font-pixel text-xs uppercase tracking-[0.06em]",

  /** Micro label — pixel font */
  h3: "font-pixel text-[0.5rem] uppercase tracking-[0.1em]",

  /** Body text — Inter */
  body: "text-[0.875rem] font-normal tracking-[0.01em]",

  /** Micro label — Inter (non-pixel variant) */
  micro: "text-[0.625rem] font-semibold uppercase tracking-[0.2em]",

  /** Large numeric — tabular, Inter */
  numericLg: "text-[1.5rem] font-bold tabular-nums tracking-[-0.02em]",

  /** Medium numeric — tabular, Inter */
  numericMd: "text-[0.875rem] font-semibold tabular-nums",

  /** Small numeric — tabular, Inter */
  numericSm: "text-[0.75rem] font-normal tabular-nums",
} as const;

export const spacing = {
  cardPadding: "p-6",
  cardPaddingLg: "p-8",
  sectionGap: "gap-6",
  gridGap: "gap-6",
} as const;

export type TypographyToken = keyof typeof typography;
export type SpacingToken = keyof typeof spacing;

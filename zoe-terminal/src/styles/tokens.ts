/**
 * Design tokens as Tailwind class strings.
 * Usage: <h1 className={cn(typography.h1, "other-classes")} />
 *
 * Sakura SNES theme — headings use pixel font, body uses Inter at 16px base.
 */

export const typography = {
  /** Pixel font heading — large (page titles) */
  h1: "font-pixel text-base uppercase tracking-[0.08em]",

  /** Pixel font heading — medium (section titles) */
  h2: "font-pixel text-sm uppercase tracking-[0.06em]",

  /** Micro label — pixel font */
  h3: "font-pixel text-[0.55rem] uppercase tracking-[0.1em]",

  /** Body text — Inter, 16px base */
  body: "text-base font-normal tracking-[0.01em]",

  /** Micro label — Inter (non-pixel variant) */
  micro: "text-xs font-semibold uppercase tracking-[0.2em]",

  /** Large numeric — KPI display, 28-36px */
  numericLg: "text-[1.75rem] font-extrabold tabular-nums tracking-tight",

  /** Medium numeric — tabular, Inter */
  numericMd: "text-base font-semibold tabular-nums",

  /** Small numeric — tabular, Inter */
  numericSm: "text-sm font-normal tabular-nums",
} as const;

export const spacing = {
  cardPadding: "p-5",
  cardPaddingLg: "p-6",
  sectionGap: "gap-6",
  gridGap: "gap-6",
} as const;

export type TypographyToken = keyof typeof typography;
export type SpacingToken = keyof typeof spacing;

/**
 * Design tokens as Tailwind class strings.
 * Usage: <h1 className={cn(typography.h1, "other-classes")} />
 */

export const typography = {
  /** 2rem / font-bold / -0.02em letter-spacing */
  h1: "text-[2rem] font-bold tracking-[-0.02em]",

  /** 1.25rem / font-semibold / -0.01em */
  h2: "text-[1.25rem] font-semibold tracking-[-0.01em]",

  /** 0.625rem / font-semibold / uppercase / 0.2em tracking (micro label) */
  h3: "text-[0.625rem] font-semibold uppercase tracking-[0.2em]",

  /** 0.875rem / font-normal / 0.01em */
  body: "text-[0.875rem] font-normal tracking-[0.01em]",

  /** 0.625rem / font-semibold / uppercase / 0.2em */
  micro: "text-[0.625rem] font-semibold uppercase tracking-[0.2em]",

  /** 1.5rem / font-bold / tabular-nums / -0.02em */
  numericLg: "text-[1.5rem] font-bold tabular-nums tracking-[-0.02em]",

  /** 0.875rem / font-semibold / tabular-nums */
  numericMd: "text-[0.875rem] font-semibold tabular-nums",

  /** 0.75rem / font-normal / tabular-nums */
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

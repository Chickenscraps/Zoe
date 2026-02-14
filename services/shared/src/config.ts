/**
 * Zoe V4 — Runtime Configuration & Validation
 * Uses Zod schemas to validate environment variables at startup.
 * Services call `loadConfig()` and get typed, validated config or a clear error.
 */
import { z } from "zod";

// ─── Schema Definitions ───────────────────────────────────────────────

const supabaseSchema = z.object({
  SUPABASE_URL: z.string().url("SUPABASE_URL must be a valid URL"),
  SUPABASE_KEY: z.string().min(1, "SUPABASE_KEY is required"),
  SUPABASE_SERVICE_ROLE_KEY: z.string().optional(),
});

const polygonSchema = z.object({
  POLYGON_API_KEY: z.string().min(1, "POLYGON_API_KEY is required"),
});

const discordSchema = z.object({
  DISCORD_TOKEN: z.string().min(1, "DISCORD_TOKEN is required"),
  DISCORD_CHANNEL_ID: z.string().min(1, "DISCORD_CHANNEL_ID is required"),
  DISCORD_GUILD_ID: z.string().optional(),
});

const researchSchema = z.object({
  GOOGLE_TRENDS_API_KEY: z.string().optional(),
  X_BEARER_TOKEN: z.string().optional(),
  BLOOMBERG_API_KEY: z.string().optional(),
});

const appSchema = z.object({
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
  TZ: z.string().default("America/New_York"),
});

// ─── Full Config Schema ───────────────────────────────────────────────

export const configSchema = appSchema
  .merge(supabaseSchema)
  .merge(polygonSchema)
  .merge(discordSchema)
  .merge(researchSchema);

export type ZoeConfig = z.infer<typeof configSchema>;

// ─── Partial Schemas (for services that only need a subset) ───────────

export const marketDataConfigSchema = appSchema.merge(polygonSchema).merge(supabaseSchema);
export type MarketDataConfig = z.infer<typeof marketDataConfigSchema>;

export const discordBotConfigSchema = appSchema.merge(supabaseSchema).merge(discordSchema);
export type DiscordBotConfig = z.infer<typeof discordBotConfigSchema>;

// ─── Loader ───────────────────────────────────────────────────────────

/**
 * Validate and load config from process.env.
 * Pass a specific schema for service-level validation, or omit for full config.
 */
export function loadConfig(): ZoeConfig;
export function loadConfig<T extends z.ZodTypeAny>(schema: T): z.infer<T>;
export function loadConfig(schema?: z.ZodTypeAny): unknown {
  const target = schema ?? configSchema;
  const result = target.safeParse(process.env);

  if (!result.success) {
    const errors = result.error.issues
      .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(`[ZoeConfig] Invalid configuration:\n${errors}`);
  }

  return result.data;
}

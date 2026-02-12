/**
 * useStrategyConfig — Hook for loading, editing, and saving strategy configs.
 *
 * Handles:
 *   - Fetching the active config for the current mode
 *   - Saving new versions with diff + audit log
 *   - Loading presets
 *   - Fetching recent audit log entries
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { supabase } from "../lib/supabaseClient";
import { MODE } from "../lib/mode";
import type { StrategyConfig } from "../lib/strategy-config";
import {
  PRESET_PROFILES,
  validateConfig,
  configChecksum,
  configDiff,
  type ValidationError,
} from "../lib/strategy-config";

export interface ConfigRow {
  id: string;
  mode: "paper" | "live";
  name: string;
  config_json: StrategyConfig;
  version: number;
  is_active: boolean;
  created_at: string;
  created_by: string;
  checksum: string;
}

export interface AuditEntry {
  id: string;
  mode: string;
  version: number;
  changed_at: string;
  changed_by: string;
  diff_json: Record<string, { old: unknown; new: unknown }>;
  reason: string | null;
}

export function useStrategyConfig() {
  const [activeConfig, setActiveConfig] = useState<ConfigRow | null>(null);
  const [draftConfig, setDraftConfig] = useState<StrategyConfig | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const initialLoadDone = useRef(false);

  // Fetch active config for current mode
  const fetchActiveConfig = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("strategy_configs")
        .select("*")
        .eq("mode", MODE)
        .eq("is_active", true)
        .limit(1)
        .maybeSingle();

      if (error) throw error;

      if (data) {
        const row: ConfigRow = {
          ...data,
          config_json: data.config_json as unknown as StrategyConfig,
        };
        setActiveConfig(row);
        // Only set draft from active if we haven't loaded yet
        if (!initialLoadDone.current) {
          setDraftConfig(row.config_json);
          initialLoadDone.current = true;
        }
      } else if (!initialLoadDone.current) {
        // No active config — use balanced preset as default
        setDraftConfig(PRESET_PROFILES.balanced.config);
        initialLoadDone.current = true;
      }
    } catch (err) {
      console.error("Failed to fetch active config:", err);
      if (!initialLoadDone.current) {
        setDraftConfig(PRESET_PROFILES.balanced.config);
        initialLoadDone.current = true;
      }
    }
  }, []);

  // Fetch recent audit log
  const fetchAuditLog = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("config_audit_log")
        .select("*")
        .eq("mode", MODE)
        .order("changed_at", { ascending: false })
        .limit(20);

      if (error) throw error;
      if (data) {
        setAuditLog(
          data.map((row) => ({
            ...row,
            diff_json: (row.diff_json ?? {}) as Record<string, { old: unknown; new: unknown }>,
          }))
        );
      }
    } catch (err) {
      console.error("Failed to fetch audit log:", err);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    async function init() {
      setLoading(true);
      await Promise.all([fetchActiveConfig(), fetchAuditLog()]);
      setLoading(false);
    }
    init();
  }, [fetchActiveConfig, fetchAuditLog]);

  // Subscribe to realtime changes
  useEffect(() => {
    const channel = supabase
      .channel("strategy_configs_changes")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "strategy_configs",
          filter: `mode=eq.${MODE}`,
        },
        () => {
          fetchActiveConfig();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [fetchActiveConfig]);

  // Validate draft whenever it changes
  useEffect(() => {
    if (draftConfig) {
      setErrors(validateConfig(draftConfig));
    }
  }, [draftConfig]);

  // Save new config version
  const saveConfig = useCallback(
    async (reason?: string): Promise<boolean> => {
      if (!draftConfig) return false;

      const validationErrors = validateConfig(draftConfig);
      if (validationErrors.length > 0) {
        setErrors(validationErrors);
        return false;
      }

      setSaving(true);
      setSaveError(null);

      try {
        const checksum = await configChecksum(draftConfig);
        const prevConfig = activeConfig?.config_json ?? null;
        const diff = prevConfig ? configDiff(prevConfig, draftConfig) : {};
        const nextVersion = (activeConfig?.version ?? 0) + 1;

        // Deactivate current active config
        if (activeConfig) {
          const { error: deactivateErr } = await supabase
            .from("strategy_configs")
            .update({ is_active: false })
            .eq("id", activeConfig.id);
          if (deactivateErr) throw deactivateErr;
        }

        // Insert new config version
        const { error: insertErr } = await supabase
          .from("strategy_configs")
          .insert({
            mode: MODE,
            name: activeConfig?.name ?? "default",
            config_json: draftConfig as unknown as Record<string, unknown>,
            version: nextVersion,
            is_active: true,
            created_by: "dashboard",
            checksum,
          });
        if (insertErr) throw insertErr;

        // Insert audit log entry
        const { error: auditErr } = await supabase
          .from("config_audit_log")
          .insert({
            mode: MODE,
            version: nextVersion,
            changed_by: "dashboard",
            diff_json: diff as unknown as Record<string, unknown>,
            reason: reason || null,
            prev_config: prevConfig as unknown as Record<string, unknown>,
            new_config: draftConfig as unknown as Record<string, unknown>,
          });
        if (auditErr) console.error("Audit log insert failed:", auditErr);

        // Refresh
        await Promise.all([fetchActiveConfig(), fetchAuditLog()]);
        return true;
      } catch (err) {
        console.error("Failed to save config:", err);
        setSaveError(err instanceof Error ? err.message : "Save failed");
        // Revert: try to restore previous active
        if (activeConfig) {
          await supabase
            .from("strategy_configs")
            .update({ is_active: true })
            .eq("id", activeConfig.id);
        }
        return false;
      } finally {
        setSaving(false);
      }
    },
    [draftConfig, activeConfig, fetchActiveConfig, fetchAuditLog]
  );

  // Load a preset profile
  const loadPreset = useCallback((presetKey: string) => {
    const preset = PRESET_PROFILES[presetKey];
    if (preset) {
      setDraftConfig(JSON.parse(JSON.stringify(preset.config)));
    }
  }, []);

  // Check if draft has unsaved changes
  const hasChanges =
    draftConfig !== null &&
    activeConfig !== null &&
    JSON.stringify(draftConfig) !== JSON.stringify(activeConfig.config_json);

  // Reset draft to active config
  const resetDraft = useCallback(() => {
    if (activeConfig) {
      setDraftConfig(JSON.parse(JSON.stringify(activeConfig.config_json)));
    }
  }, [activeConfig]);

  return {
    activeConfig,
    draftConfig,
    setDraftConfig,
    auditLog,
    loading,
    saving,
    errors,
    saveError,
    hasChanges,
    saveConfig,
    loadPreset,
    resetDraft,
    fetchActiveConfig,
  };
}

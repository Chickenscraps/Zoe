import { useCallback, useEffect, useState } from 'react';
import type { Json } from '../lib/types';
import { supabase } from '../lib/supabaseClient';

export interface DialConfig {
  key: string;
  label: string;
  type: 'boolean' | 'number';
  min?: number;
  max?: number;
  step?: number;
  description: string;
}

const DIAL_DEFS: DialConfig[] = [
  { key: 'kill_switch', label: 'Kill Switch', type: 'boolean', description: 'Pause all trading immediately' },
  { key: 'scan_interval_s', label: 'Scan Interval', type: 'number', min: 15, max: 300, step: 15, description: 'Seconds between scanner sweeps' },
  { key: 'min_score', label: 'Min Score', type: 'number', min: 0, max: 100, step: 5, description: 'Minimum scanner score to consider' },
  { key: 'max_pct_per_trade', label: 'Max % Per Trade', type: 'number', min: 1, max: 100, step: 1, description: '% of buying power allowed per single trade (1-100%)' },
  { key: 'stop_loss_pct', label: 'Stop Loss %', type: 'number', min: 0.5, max: 10, step: 0.5, description: 'Default stop loss percentage' },
];

export function useDials() {
  /** Saved values from Supabase (source of truth) */
  const [savedValues, setSavedValues] = useState<Record<string, unknown>>({});
  /** Local draft values (may differ from saved) */
  const [draftValues, setDraftValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const keys = DIAL_DEFS.map(d => d.key);
        const { data } = await supabase
          .from('config')
          .select('key, value')
          .in('key', keys);
        if (data) {
          const map: Record<string, unknown> = {};
          for (const row of data) {
            map[row.key] = row.value;
          }
          setSavedValues(map);
          setDraftValues(map);
        }
      } catch (err) {
        console.error('Failed to load dials:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  /** Update a draft value locally (does NOT save to DB) */
  const setValue = useCallback((key: string, value: unknown) => {
    setDraftValues(prev => ({ ...prev, [key]: value }));
  }, []);

  /** Detect which keys have been changed vs saved values */
  const changedKeys = Object.keys(draftValues).filter(
    key => JSON.stringify(draftValues[key]) !== JSON.stringify(savedValues[key])
  );
  const hasChanges = changedKeys.length > 0;

  /** Apply all pending changes to Supabase in a batch */
  const applyChanges = useCallback(async () => {
    if (changedKeys.length === 0) return;
    setApplying(true);
    try {
      const upserts = changedKeys.map(key => ({
        key,
        value: draftValues[key] as Json,
      }));
      const { error } = await supabase.from('config').upsert(upserts);
      if (error) throw error;

      // Audit log for each changed dial
      const auditRows = changedKeys.map(key => ({
        event_type: 'config_change',
        message: `Dial ${key} set to ${JSON.stringify(draftValues[key])}`,
        metadata: { key, value: draftValues[key] as Json, source: 'copilot_dials' },
      }));
      await supabase.from('audit_log').insert(auditRows);

      // Update saved values to match draft
      setSavedValues(prev => {
        const next = { ...prev };
        for (const key of changedKeys) {
          next[key] = draftValues[key];
        }
        return next;
      });
    } catch (err) {
      console.error('Failed to apply dials:', err);
      // Rollback draft to saved
      setDraftValues({ ...savedValues });
    } finally {
      setApplying(false);
    }
  }, [changedKeys, draftValues, savedValues]);

  /** Discard pending changes and revert to saved values */
  const discardChanges = useCallback(() => {
    setDraftValues({ ...savedValues });
  }, [savedValues]);

  return {
    dials: DIAL_DEFS,
    values: draftValues,
    loading,
    applying,
    hasChanges,
    setValue,
    applyChanges,
    discardChanges,
  };
}

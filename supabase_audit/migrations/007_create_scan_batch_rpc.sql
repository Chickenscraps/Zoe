-- 007_create_scan_batch_rpc.sql
-- P2-2: Server-side function to get latest scan batch in one round trip
-- Replaces the 2-query pattern used in 5+ places
-- Reversible: DROP FUNCTION

CREATE OR REPLACE FUNCTION get_latest_scan_batch(p_mode TEXT)
RETURNS SETOF candidate_scans
LANGUAGE sql
STABLE
AS $$
  SELECT cs.*
  FROM candidate_scans cs
  WHERE cs.mode = p_mode
    AND cs.created_at = (
      SELECT MAX(created_at)
      FROM candidate_scans
      WHERE mode = p_mode
    )
  ORDER BY cs.score DESC;
$$;

-- Grant anon access to call this function
GRANT EXECUTE ON FUNCTION get_latest_scan_batch(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION get_latest_scan_batch(TEXT) TO authenticated;

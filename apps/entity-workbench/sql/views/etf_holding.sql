CREATE OR REPLACE VIEW ontology_view.etf_holding AS
SELECT mapped.*,
       CASE WHEN EXISTS (SELECT 1 FROM public.equity_profile ep WHERE ep.instrument_id=mapped.constituent_instrument_id) THEN 'EQUITY' WHEN EXISTS (SELECT 1 FROM public.etf_profile et WHERE et.instrument_id=mapped.constituent_instrument_id) THEN 'ETF' END::text AS security_type
FROM (
SELECT ('[' || to_json(base.etf_instrument_id::text)::text || ',' || to_json(base.constituent_instrument_id::text)::text || ',' || to_json(base.trade_date::text)::text || ']')::text AS id,
       (base.etf_instrument_id)::text AS etf_instrument_id,
       (base.constituent_instrument_id)::text AS constituent_instrument_id,
       (base.trade_date)::date AS trade_date,
       (base.weight_ratio)::double precision AS weight_ratio,
       (base.available_at)::timestamptz AS available_at
FROM public.etf_holding_snapshot AS base
) AS mapped;

CREATE OR REPLACE VIEW ontology_view.security_industry_classification AS
SELECT mapped.*,
       CASE WHEN EXISTS (SELECT 1 FROM public.equity_profile ep WHERE ep.instrument_id=mapped.instrument_id) THEN 'EQUITY' WHEN EXISTS (SELECT 1 FROM public.etf_profile et WHERE et.instrument_id=mapped.instrument_id) THEN 'ETF' END::text AS security_type
FROM (
SELECT ('[' || to_json(base.instrument_id::text)::text || ',' || to_json(base.as_of_date::text)::text || ']')::text AS id,
       (base.instrument_id)::text AS instrument_id,
       (base.as_of_date)::date AS snapshot_date,
       (base.sector_name)::text AS sector_name,
       (base.industry_name)::text AS industry_name,
       (base.source)::text AS source,
       (base.available_at)::timestamptz AS available_at,
       (NULL)::date AS effective_from
FROM public.instrument_classification AS base
) AS mapped;

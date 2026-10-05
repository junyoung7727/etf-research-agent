CREATE OR REPLACE VIEW ontology_view.exchange_security_classification AS
SELECT mapped.*,
       CASE WHEN EXISTS (SELECT 1 FROM public.equity_profile ep WHERE ep.instrument_id=mapped.security_id) THEN 'EQUITY' WHEN EXISTS (SELECT 1 FROM public.etf_profile et WHERE et.instrument_id=mapped.security_id) THEN 'ETF' END::text AS security_type
FROM (
SELECT ('[' || to_json(base.market::text)::text || ',' || to_json(base.instrument_code::text)::text || ',' || to_json(base.as_of_date::text)::text || ',' || to_json(base.raw_run_id::text)::text || ']')::text AS id,
       (base.market)::text AS market,
       (base.instrument_code)::text AS instrument_code,
       (base.standard_code)::text AS standard_code,
       (base.name_kr)::text AS name_kr,
       (base.security_group)::text AS security_group,
       (base.as_of_date)::date AS collected_on,
       (base.large_code)::text AS large_code,
       (base.large_name)::text AS large_name,
       (base.medium_code)::text AS medium_code,
       (base.medium_name)::text AS medium_name,
       (base.small_code)::text AS small_code,
       (base.small_name)::text AS small_name,
       (base.taxonomy)::text AS taxonomy,
       (base.available_at)::timestamptz AS available_at,
       (SELECT i.instrument_id FROM public.instrument i WHERE i.ticker=base.instrument_code AND i.market_code=CASE base.market WHEN 'KOSPI' THEN 'XKRX' WHEN 'KOSDAQ' THEN 'XKOS' END AND i.instrument_type IN ('EQUITY','ETF'))::text AS security_id
FROM public.sector_classification AS base
) AS mapped;

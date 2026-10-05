CREATE OR REPLACE VIEW ontology_view.daily_nav AS
SELECT mapped.*,
       mapped.nav::text AS nav_decimal_text
FROM (
SELECT ('[' || to_json(base.etf_instrument_id::text)::text || ',' || to_json(base.trade_date::text)::text || ']')::text AS id,
       (base.etf_instrument_id)::text AS etf_instrument_id,
       (base.trade_date)::date AS trade_date,
       (base.nav)::numeric AS nav,
       (base.available_at)::timestamptz AS available_at
FROM public.etf_nav_daily AS base
) AS mapped;

CREATE OR REPLACE VIEW ontology_view.intraday_investor_flow AS
SELECT mapped.*,
       CASE WHEN EXISTS (SELECT 1 FROM public.equity_profile ep WHERE ep.instrument_id=mapped.instrument_id) THEN 'EQUITY' WHEN EXISTS (SELECT 1 FROM public.etf_profile et WHERE et.instrument_id=mapped.instrument_id) THEN 'ETF' END::text AS security_type
FROM (
SELECT ('[' || to_json(base.instrument_id::text)::text || ',' || to_json(base.trade_date::text)::text || ',' || to_json(base.asof_slot::text)::text || ']')::text AS id,
       (base.instrument_id)::text AS instrument_id,
       (base.trade_date)::date AS trade_date,
       (base.asof_slot)::text AS reporting_slot_code,
       (base.net_qty_foreign_est)::bigint AS foreign_net_purchase_quantity_estimate,
       (base.net_qty_institution_est)::bigint AS institutional_net_purchase_quantity_estimate,
       (base.net_qty_total_est)::bigint AS foreign_and_institutional_net_purchase_quantity_estimate,
       (base.available_at)::timestamptz AS available_at,
       (NULL)::timestamptz AS estimate_as_of
FROM public.investor_flow_intraday AS base
) AS mapped;

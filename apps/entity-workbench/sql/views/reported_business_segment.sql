CREATE OR REPLACE VIEW ontology_view.reported_business_segment AS
SELECT mapped.*,
       mapped.revenue_krw::text AS revenue_krw_decimal_text,
       mapped.revenue_total_krw::text AS revenue_total_krw_decimal_text
FROM (
SELECT (base.fact_id::text)::text AS id,
       (base.segment_name)::text AS segment_name,
       (base.concept_id)::text AS concept_id,
       (base.period_label)::text AS reported_period_text,
       (base.revenue_krw)::numeric AS revenue_krw,
       (base.revenue_share_pct)::double precision AS revenue_share_pct,
       (CASE base.share_basis WHEN 'REPORTED' THEN 'REPORTED' WHEN 'COMPUTED' THEN 'COMPUTED' WHEN 'RESCALED' THEN 'RESCALED' WHEN 'UNRELIABLE' THEN NULL END)::text AS share_calculation_method,
       (fact.document_id)::text AS document_id,
       (fact.available_at)::timestamptz AS available_at,
       (NULL)::date AS period_start,
       (NULL)::date AS period_end,
       (NULL)::text AS statement_basis,
       (NULL)::numeric AS revenue_total_krw,
       (NULL)::text AS revenue_total_scope
FROM public.business_segment_fact AS base
LEFT JOIN public.disclosure_fact AS fact ON base.fact_id = fact.fact_id AND base.fact_type = fact.fact_type
) AS mapped;

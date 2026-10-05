CREATE OR REPLACE VIEW ontology_view.financial_report_snapshot AS
SELECT ('[' || to_json(base.corp_code::text)::text || ',' || to_json(base.fiscal_year::text)::text || ',' || to_json(base.reprt_code::text)::text || ',' || to_json(base.fs_basis::text)::text || ',' || to_json(base.raw_run_id::text)::text || ']')::text AS id,
       (base.corp_code)::text AS corp_code,
       (base.instrument_code)::text AS instrument_code,
       (base.fiscal_year)::smallint AS fiscal_year,
       (base.reprt_code)::text AS report_type_code,
       (CASE base.report_period WHEN 'Q1' THEN 'Q1' WHEN 'Q2' THEN 'H1' WHEN 'Q3' THEN '9M' WHEN 'Q4' THEN 'FY' END)::text AS report_coverage,
       (base.fs_basis)::text AS fs_basis,
       (base.rcept_no)::text AS receipt_number,
       (base.rcept_date)::date AS receipt_date,
       (base.available_at)::timestamptz AS available_at,
       (base.received_at)::timestamptz AS received_at,
       (base.availability_basis)::text AS availability_basis,
       (SELECT c.actor_id FROM public.company_profile c WHERE c.dart_corp_code=base.corp_code)::text AS company_id
FROM public.financial_report_version AS base;

CREATE OR REPLACE VIEW ontology_view.disclosure AS
SELECT (base.document_id::text)::text AS id,
       (base.issuer_actor_id)::text AS issuer_id,
       (base.disclosure_type)::text AS disclosure_type,
       (base.report_date)::date AS report_date,
       (document.title)::text AS title,
       (document.published_at)::timestamptz AS published_at,
       (document.available_at)::timestamptz AS available_at,
       (document.source_document_id)::text AS source_document_id,
       (document.source_uri)::text AS source_uri
FROM public.disclosure_document AS base
LEFT JOIN public.document AS document ON base.document_id = document.document_id AND base.document_type = document.document_type;

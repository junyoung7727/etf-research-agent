CREATE OR REPLACE VIEW ontology_view.source_event AS
SELECT base.source_event_id::text AS id,
       base.event_type_code::text AS event_type,
       base.predicate_code::text AS predicate,
       base.source_class::text AS source_class,
       base.event_date::date AS event_date,
       base.available_at::timestamptz AS available_at,
       base.lifecycle_stage::text AS lifecycle_stage
FROM public.source_event AS base;

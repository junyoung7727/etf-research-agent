CREATE OR REPLACE VIEW ontology_view.event_thread AS
SELECT (base.thread_id::text)::text AS id,
       (base.event_type_code)::text AS event_type,
       (NULL)::text AS current_stage,
       (base.opened_at)::timestamptz AS opened_at,
       (NULL)::timestamptz AS last_state_at
FROM public.event_thread AS base;

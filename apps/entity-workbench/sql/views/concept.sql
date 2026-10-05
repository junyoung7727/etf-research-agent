CREATE OR REPLACE VIEW ontology_view.concept AS
SELECT (base.concept_id::text)::text AS id,
       (entity.display_name)::text AS name,
       (base.concept_type)::text AS concept_type,
       (base.parent_concept_id)::text AS parent_concept_id
FROM public.concept AS base
LEFT JOIN public.entity AS entity ON base.concept_id = entity.entity_id AND base.entity_type = entity.entity_type;

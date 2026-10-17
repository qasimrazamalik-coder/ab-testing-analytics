-- Fails (returns a row) unless exactly two variants are present.
select *
from (
    select count(distinct variant) as n_variants
    from {{ ref('fct_experiment_users') }}
) as t
where n_variants <> 2

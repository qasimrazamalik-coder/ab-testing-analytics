-- Coarse sanity bound on the 50/50 design: control share must sit inside 45%-55%.
-- The statistically exact sample-ratio test (chi-square) runs in Python: src/abtest/stats.py.
select *
from (
    select 1.0 * sum(case when arm = 'control' then 1 else 0 end) / count(*) as control_share
    from {{ ref('fct_experiment_users') }}
) as t
where control_share < 0.45 or control_share > 0.55

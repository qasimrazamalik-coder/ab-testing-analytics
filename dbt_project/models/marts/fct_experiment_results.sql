-- Grain: one row per variant. Inference (tests, intervals, decision) happens in Python;
-- this model only publishes the audited counts those tests consume.
select
    variant,
    arm,
    count(*) as users,
    sum(retained_d1) as retained_d1_users,
    sum(retained_d7) as retained_d7_users,
    1.0 * sum(retained_d1) / count(*) as retention_d1,
    1.0 * sum(retained_d7) / count(*) as retention_d7,
    avg(1.0 * game_rounds) as avg_game_rounds,
    sum(is_zero_round_user) as zero_round_users
from {{ ref('fct_experiment_users') }}
group by variant, arm

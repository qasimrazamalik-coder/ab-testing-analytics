-- Grain: one row per user. The control variant is configured once (var control_variant).
select
    user_id,
    variant,
    case when variant = '{{ var("control_variant", "gate_30") }}' then 'control' else 'treatment' end as arm,
    game_rounds,
    retained_d1,
    retained_d7,
    case when game_rounds = 0 then 1 else 0 end as is_zero_round_user
from {{ ref('stg_cookie_cats') }}

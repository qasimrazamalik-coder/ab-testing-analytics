-- Fails (returns rows) for any user with a negative round count.
select user_id, game_rounds
from {{ ref('fct_experiment_users') }}
where game_rounds < 0

-- One row per user: typed and renamed, nothing else. No business logic lives in staging.
select
    cast(userid as bigint) as user_id,
    cast(version as varchar) as variant,
    cast(sum_gamerounds as integer) as game_rounds,
    case when lower(cast(retention_1 as varchar)) in ('true', '1') then 1 else 0 end as retained_d1,
    case when lower(cast(retention_7 as varchar)) in ('true', '1') then 1 else 0 end as retained_d7
from {{ source('raw', 'cookie_cats') }}

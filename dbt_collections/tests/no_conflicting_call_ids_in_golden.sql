select call_id
from {{ ref('golden_call_events') }}
group by call_id
having count(*) > 1

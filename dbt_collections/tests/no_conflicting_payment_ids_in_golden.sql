select payment_id
from {{ ref('golden_successful_payments') }}
group by payment_id
having count(*) > 1

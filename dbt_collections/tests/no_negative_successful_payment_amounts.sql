select payment_id
from {{ ref('golden_successful_payments') }}
where amount < 0

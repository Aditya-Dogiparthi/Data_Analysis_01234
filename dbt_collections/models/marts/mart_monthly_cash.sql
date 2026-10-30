{{ config(materialized='table') }}
select date_trunc('month', event_at_source)::date as event_month,
       count(*) filter (where payment_status='SUCCESS') as successful_payment_events,
       sum(amount) filter (where payment_status='SUCCESS') as gross_successful_collections,
       count(*) filter (where payment_status='REVERSED') as reversal_events,
       sum(amount) filter (where payment_status='REVERSED') as reversal_amount_reported_separately
from {{ ref('golden_payment_events') }}
group by 1

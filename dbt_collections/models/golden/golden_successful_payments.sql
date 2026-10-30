{{ config(materialized='table') }}
select *
from {{ ref('golden_payment_events') }}
where payment_status = 'SUCCESS'
  and amount >= 0

{{ config(materialized='view') }}
select
  payment_id::text as payment_id,
  account_id::text as account_id,
  borrower_id::text as borrower_id,
  event_at::timestamp as event_at_source,
  payment_reference::text as payment_reference,
  amount::numeric(18,2) as amount,
  upper(payment_status::text) as payment_status,
  payment_method::text as payment_method,
  provider_id::text as provider_id
from {{ source('collections_raw','payments') }}

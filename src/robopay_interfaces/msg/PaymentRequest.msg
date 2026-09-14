# An invoice: one robot asking another to pay for a service.


string request_id      # unique id for this invoice, so duplicates are recognisable
string payee_address   # who to pay
string amount          # decimal string, e.g. "2.50"
string asset           # "USDC"
string memo            # what the charge is for
string settlement      # "direct" | "escrow"
string terms_hash      # optional: hash of the agreed terms
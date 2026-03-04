"""
Cloud-agnostic verification helpers.

Modules:
  verify_config       - Timeouts, retriable HTTP codes (from env)
  verify_csv          - get_total_rec_from_csv (expected records from fridge_sales CSV)
  verify_sse          - SSE parsing, QueryStream error classification
  verify_api_endpoints - Poll Health/Version/Frontend/QueryStream/Analytics
  verify_llm_client   - Local LLM client instantiation check
  verify_kubectl      - verify_kubectl_namespace_gone (teardown namespace check)
  verify_summary      - VerifyRow, print_verify_summary (table output)
"""

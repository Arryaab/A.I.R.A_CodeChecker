# task_064_ssrf_url_scheme_validation

**Category**: security_defect
**Difficulty**: hard

## Description
Harden outgoing URL validator against SSRF and non-HTTP protocol schemes

## Expected Behavior
Only allows http/https schemes and rejects loopback, link-local, and private IP addresses

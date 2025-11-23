# Tenant Onboarding Guide

## Steps to Onboard a New Tenant
1. **Create Tenant Profile**: Via Admin UI/API, generate tenantId and provision isolated resources (DB schema, RAG index).
2. **Upload Artifacts**: Load Domain Pack JSON (validate schema); upload Tenant Policy Pack JSON (merge with Domain Pack).
3. **Configure Tools**: Register approved tools via registry; provide endpoints and auth.
4. **Initialize RAG**: Seed with initial examples from packs; run embedding job.
5. **Activate Playbooks**: Validate and enable custom/domain playbooks.
6. **Set Up Monitoring Dashboards**: Configure tenant-specific views in observability system; set alerts.
7. **Test Pipeline**: Ingest sample exceptions; verify end-to-end flow.
8. **Go-Live**: Enable ingestion connectors; monitor initial runs.

Required Artifacts: Domain Pack JSON, Tenant Policy Pack JSON, Tools configurations (endpoints/auth). Ensure compliance with safety rules before activation.
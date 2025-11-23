# Security & Compliance Checklist

- **Role-Based Access Controls**: Implement RBAC with roles (admin, operator, viewer); tenant-scoped permissions.
- **Tenant Isolation Requirements**: DB partitioning, namespaced storage, encrypted channels; annual penetration tests.
- **Tool Allow-List Enforcement**: Runtime checks; reject unregistered tools.
- **Sensitive Data Controls**: Encryption at rest/transit (AES-256); PII masking in logs; GDPR-compliant retention.
- **Explainability**: All decisions include evidence; traceable to packs.
- **Regulatory Alignment**: SOC2 (auditing, access controls); ISO27001 (risk management); FINRA/HIPAA via domain-specific guardrails if packs require.
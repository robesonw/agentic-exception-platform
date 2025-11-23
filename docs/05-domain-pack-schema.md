# Domain Pack Schema (Full Specification)

## Ontology Model
Object defining domain concepts: {concepts: object (key: conceptName, value: {definition: string, synonyms: array})}.

## Entity Definitions
Object: {entityName: {attributes: object (key: attrName, value: {type: string, required: boolean}), relations: array of {toEntity: string, type: string}}}.

## Exception Taxonomy Model
Object: {typeName: {description: string, parentType: string (for hierarchy), detectionRules: array of {condition: string (e.g., JSONPath query)}}}.

## Severity Rules
Array: [{condition: string (e.g., 'exceptionType == "CriticalFailure"'), severity: string, priorityScore: integer}].

## Playbook Format
Array: [{exceptionType: string, steps: array of {action: string (e.g., 'invokeTool'), parameters: object, conditional: string, fallback: string}]}.

## Guardrails Format
Object: {allowLists: {tools: array, actions: array}, blockLists: {tools: array, actions: array}, humanApprovalThreshold: float (0.0-1.0 for confidence), severityGates: object (severity: {requireApproval: boolean})}.

## Tool Definition Model
Object: {toolName: {description: string, parameters: object (key: paramName, value: {type: string, required: boolean}), endpoint: string, auth: object (e.g., {type: 'apiKey'})}}.
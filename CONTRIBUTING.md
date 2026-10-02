# Contributing

## Engineering standards

Changes should be:

- reproducible
- testable
- documented
- traceable
- appropriately scoped

## Validation

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Commit conventions

Preferred prefixes:

```text
feat:
fix:
refactor:
test:
docs:
security:
build:
ci:
release:
```

Example:

```text
feat: improve deterministic position sizing
```

## Historical material

Do not rewrite historical release artifacts merely to make them look cleaner.
Use the provenance layer to explain discrepancies and lineage.

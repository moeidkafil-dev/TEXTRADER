## Summary

<!-- What changed and why? -->

## Scope

- [ ] Source
- [ ] Tests
- [ ] Documentation
- [ ] Security
- [ ] Performance
- [ ] Release / provenance

## Validation

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Risk / Compatibility

<!-- Describe behavior changes and operational risk. -->

## Checklist

- [ ] No secrets added
- [ ] Tests updated where needed
- [ ] Documentation updated
- [ ] Historical artifacts preserved
- [ ] Provenance implications reviewed

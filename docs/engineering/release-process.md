# Release Process

## Validate

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Inspect

```bash
git status
git diff
git diff --cached
```

## Commit

```bash
git add -A
git commit -m "release: TEXTRADER X vX.Y.Z"
```

## Annotated tag

```bash
git tag -a vX.Y.Z -m "TEXTRADER X vX.Y.Z"
```

## Verify

```bash
git show vX.Y.Z
git tag --verify vX.Y.Z
```

## Push

```bash
git push origin main
git push origin vX.Y.Z
```

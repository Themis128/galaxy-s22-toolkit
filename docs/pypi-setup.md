# Enabling PyPI publishing (one-time, ~2 minutes)

The `publish-pypi` CI job is gated on the repo variable `ENABLE_PYPI`
(`b1d4672`): releases stay green with publishing skipped until both of
the following are done.

## 1. Configure the trusted publisher on pypi.org

1. Go to <https://pypi.org> and sign in.
2. Your account -> Publishing -> **Add a new pending publisher** (or, if
   the project already exists, project -> Settings -> Publishing).
3. Fill in exactly:
   - **PyPI project name**: `galaxy-s22-toolkit` (must match
     `phone-lib/pyproject.toml` `name`)
   - **Owner**: `Themis128`
   - **Repository**: `galaxy-s22-toolkit`
   - **Workflow filename**: `ci.yml`
   - **Environment**: leave empty (the job defines `id-token: write`
     directly)
4. Save.

## 2. Opt in on GitHub

1. Repo -> Settings -> Secrets and variables -> Actions -> **Variables**
   tab -> New repository variable:
   - Name: `ENABLE_PYPI`, Value: `true`
2. Create the next release (or re-publish v0.3.0 by deleting and
   re-drafting it) — the `Publish to PyPI` job will then upload the
   wheel built by `Build Wheel`.

## Notes

- The version in `phone-lib/pyproject.toml` must be new to PyPI; a
  version can never be re-uploaded.
- To publish the already-released v0.3.0: after configuring the above,
  run the `Publish to PyPI` job manually from the v0.3.0 release run
  via *Re-run jobs* is NOT possible for skipped jobs — tag a patch
  release (e.g. `v0.3.1`) instead.

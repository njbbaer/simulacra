# lab

Replays logged turns through the production generator and runs them in resumable batches. Experiment harnesses build on `src.lab` rather than simulacra's internals, so they test what production sends; see its exports and their docstrings.

Harnesses outside the repo put the repo root on `sys.path` and run with `uv run --project <repo> python`. Importing `src.lab` loads the repo's `.env`.

- Replay from a snapshot (`take_snapshot`) to keep edits to the live characters during a batch out of it.
- Group batch jobs by shared prompt prefix, usually the turn. Each group's first call warms the cache for the rest.
- Check the prompt hashes in results to confirm that conditions differ where they should.

A harness may work around lab for a one-off need. A need that comes up again belongs in lab.

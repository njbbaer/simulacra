# lab

Replays logged turns through the production generator and runs them in resumable batches. Experiment harnesses build on `src.lab` rather than simulacra's internals, so they test what production sends. See its exports and their docstrings.

Harnesses outside the repo put the repo root on `sys.path` and run with `uv run --project <repo> python`. Importing `src.lab` loads the repo's `.env`. Load another experiment's module by its file path with `importlib`, since experiment folders reuse names like `run.py` and `check.py` and a `sys.path` import silently returns whichever loaded first.

- Draw turns with `sample_turns` and save them, so reruns use the same selection.
- Replay from a snapshot (`take_snapshot`) to keep edits to the live characters during a batch out of it. Give prompt changes as snapshot edits rather than editing the copy by hand.
- Call judges and other models with `complete`, and return `totals` of every result in a job so the log and the plan limit see all its calls.
- Group batch jobs by shared prompt prefix, usually the turn. Each group's first job warms the cache for the rest. Pass `warm_by` with a coarser key, usually the character, so its system prompt is cached once before the groups fan out. The line at the end of a batch shows the cached share of the jobs after each group's first.
- When conditions share a prompt prefix, as a judge's conversation does, put every condition for a (turn, sample) into one job. The group's first job then warms all of them.
- Concurrency counts jobs, not calls. A job that gathers k calls can have k × concurrency calls in flight.
- Check the prompt hashes in results to confirm that conditions differ where they should.
- Split responses with `sections` and number spoken sentences with `sentences`, which numbers them as his sentence marks do.
- Size a run from a pilot with `Pilot` before running it, and report with `paired_effect`, whose `below` is the share of resamples where the treatment came out below the base.

A harness may work around lab for a one-off need. A need that comes up again belongs in lab.

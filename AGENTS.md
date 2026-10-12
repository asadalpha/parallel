# Working in Parallel

- Treat `docs/guide.md` as the self-contained product/config reference (the earlier `PRD.MD` was consolidated into it). Ask before changing its selected stack or MVP boundaries.
- Keep the web app in `apps/frontend` and the API in `apps/backend`; avoid coupling the frontend directly to the database.
- Preserve the distinction between published content and drafts/submissions in any future public API work.
- Do not create fictional story records or imply that illustrative content is real. Use clearly identified fixtures for tests.
- Keep AI, maps, and audio integrations optional until their providers and credentials are configured.
- Run the frontend typecheck/linter and backend tests/linter for changes in those apps. See `SETUP.md` for commands.
- Never push to a shared branch without the user's explicit approval. Commit locally, then ask.

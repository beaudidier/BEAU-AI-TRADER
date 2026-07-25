# Codex Automation Rules

These rules apply permanently to the entire repository.

1. Automate every technically possible step.
2. Do not ask the user to edit files, copy SQL, run terminal commands, commit, push, restart services, or apply migrations manually when you can do it yourself.
3. Use the project terminal for installations and commands.
4. Use the linked Supabase CLI for migrations.
5. Run focused tests, build, and lint when relevant.
6. Commit every completed milestone with the requested message.
7. Push to `origin/main` after a successful commit.
8. Never expose, print, stage, or commit secrets.
9. Pause only when human interaction is unavoidable:
   - Browser authentication
   - Password or token entry
   - Destructive approval
   - Genuinely ambiguous product decisions
10. After every milestone, report:
    - What changed
    - Tests run
    - Commit hash
    - Push status
    - Migrations applied
    - Remaining manual action
11. Do not start the next milestone automatically.
12. Preserve unrelated uncommitted work.

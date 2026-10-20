# Frontend Conventions

RestoCore initially uses Django templates and HTMX. Tailwind will be introduced as a separate tooling change.

## Reuse boundaries

- `templates/layouts/` owns full-page shells.
- `templates/components/navigation/` owns shared navigation and page chrome.
- `templates/components/feedback/` owns alerts, messages, validation summaries, and loading states.
- App-specific fragments stay under that app's template namespace until they are genuinely shared.
- HTMX response fragments must be small templates rather than copied HTML strings inside views.

Do not create a generic component merely because two elements look similar. Extract a shared component when they share behavior, accessibility requirements, or a stable visual contract.

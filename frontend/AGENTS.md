<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Architecture rules

- All mock/demo data lives in `src/lib/mockApi.ts` and is reached only through `src/lib/api.ts` (base URL from `VITE_API_BASE_URL`) — so a real backend can replace it without touching UI.
- Shared domain types live in `src/types/spatial.ts`; page sections live in `src/sections/`, reusable UI in `src/components/`.
- Three.js work lives in `src/components/three/` and renders client-side only, with the frame loop gated on viewport visibility and `prefers-reduced-motion` for performance.

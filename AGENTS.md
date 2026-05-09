# Agent rules for jumpyloo-website

- Issue tracker is on **foculoom/foculoom-project**. Reference issues with the full path: `foculoom/foculoom-project#N`.
- All PRs must include `Closes foculoom/foculoom-project#N` in the body.
- Brand assets sourced from `foculoombrand/` ONLY. No external CDN, no external font/icon downloads.
- Default branch: `master`.
- Custom domain: `jumpyloo.com` (Cloudflare DNS, GitHub Pages cert).
- Cloudflare proxy MUST stay grey-cloud (DNS-only) for `jumpyloo.com` records during cert provisioning.
- No client-side trackers, no cookies, no JavaScript in v1 landing page (Trust Posture v2).

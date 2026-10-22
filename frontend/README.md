# Inkloom Sentinel — Frontend Architecture & Design System

## Overview
Inkloom Sentinel is an evidence-backed brand compliance and content governance platform. The frontend is built with React 19, TypeScript, Vite, Tailwind CSS, and Lucide icons, connecting directly to the FastAPI backend API contracts.

## Visual Identity & Color System
The visual language avoids generic SaaS blue palettes in favor of an unmistakable editorial and cinematic identity:
- **Obsidian (`#191916`)**: Cinematic sections, primary contrast background.
- **Deep Charcoal (`#252520`)**: Secondary surfaces, cards, and deep contrast borders.
- **Warm Ivory (`#F4F0E8`)**: Editorial marketing backdrop and page canvas.
- **Paper White (`#FBF9F4`)**: Editorial surfaces, data tables, and input backgrounds.
- **Burnt Copper (`#B96B49`)**: Primary accent, badges, and active state highlights.
- **Soft Copper (`#D79570`)**: Subtle highlights and micro-interactions.
- **Muted Chartreuse (`#C5CF78`)**: Verified/compliant status markers and evidence signals.
- **Secondary Text (`#77766E`)**: Secondary labels and meta-information.
- **Borders (`rgba(37,37,32,0.12)`)**: Subtle separators with high legibility.

## Typography
- **Headlines & Editorial Accents**: Instrument Serif (loaded via Google Fonts).
- **Primary Body & UI**: Barlow and Helvetica Neue Light with fallback to Helvetica and Arial.
- **Display Wordmarks**: Playfair Display, Oswald, Montserrat, Roboto Slab, and Raleway.

## Asset Registry
All supplied media assets are preserved in `src/config/assets.ts`:
- **Asset A**: Palomar hero video (`hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4`)
- **Asset B**: RIVR hero video (`hf_20260428_193507_4286c423-2fd9-4efd-92bd-91a939453fc1.mp4`)
- **Asset C**: Cinematic space hero video (`hf_20260418_080021_d598092b-c4c2-4e53-8e46-94cf9064cd50.mp4`)
- **Asset D**: Cinematic capabilities video (`hf_20260418_094631_d30ab262-45ee-4b7d-99f3-5d5848c8ef13.mp4`)
- **Asset E**: Driftbar meadow footer video (`4d01c727-d9c5-47c8-a778-35a451ffd39f.mp4`)
- **Asset F**: Driftbar footer poster (`hf_20261014_121838_c97d0940-f430-4304-8573-4f47ee44f447.png`)
- **Corner Mask SVGs**: Exact Top Intersection and Left Intersection mask paths for liquid-glass corners.

## Routes & Pages
- `/`: Public marketing landing page (Palomar navbar & hero, RIVR corner masks, word-by-word BlurText, capabilities, Driftbar meadow paper-fade footer).
- `/login`: User authentication with session persistence.
- `/signup`: User registration and instant onboarding.
- `/app`: Workspace governance dashboard (metrics, recent submissions, active policies, quick actions).
- `/app/policies`: Policy management, rules breakdown, version tags, and draft creation.
- `/app/submissions`: Submissions list, revision selector, new submission modal, and verification runner.
- `/app/evidence`: Evidence source registry, claim discovery status, verification links.
- `/app/reviews`: Unified review workspace, deterministic findings, claim assessments, correction proposals.
- `/app/audit`: Searchable audit trail with event filtering and actor provenance.
- `/app/analytics`: Content compliance breakdown, verification velocity, turnaround time metrics.
- `/app/settings`: Workspace configuration, RBAC member management, role permissions.

## Local Development
1. Start backend:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. Start frontend dev server:
   ```bash
   npm run dev
   ```
3. Build for production:
   ```bash
   npm run build
   ```

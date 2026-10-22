/**
 * Inkloom Sentinel — Asset Registry
 *
 * Preserves all explicitly supplied video and poster URLs with exact settings
 * and reference parameters.
 */

export const ASSETS = {
  // Asset A — Palomar hero video (full viewport landscape)
  PALOMAR_HERO_VIDEO:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260820_010308_b1636845-4c15-4ab6-b0c9-9a29bfb0c6e3.mp4',

  // Asset B — RIVR hero video (rounded frame)
  RIVR_HERO_VIDEO:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260428_193507_4286c423-2fd9-4efd-92bd-91a939453fc1.mp4',

  // Asset C — Cinematic space hero video
  CINEMATIC_SPACE_HERO_VIDEO:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260418_080021_d598092b-c4c2-4e53-8e46-94cf9064cd50.mp4',

  // Asset D — Cinematic capabilities video
  CINEMATIC_CAPABILITIES_VIDEO:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260418_094631_d30ab262-45ee-4b7d-99f3-5d5848c8ef13.mp4',

  // Asset E — Driftbar meadow footer video
  DRIFTBAR_FOOTER_MEADOW_VIDEO:
    'https://d2ol7oe51mr4n9.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/4d01c727-d9c5-47c8-a778-35a451ffd39f.mp4',

  // Asset F — Driftbar footer poster
  DRIFTBAR_FOOTER_POSTER:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20261014_121838_c97d0940-f430-4304-8573-4f47ee44f447.png',
} as const

// Corner mask SVG paths for RIVR-inspired bottom-right cutout pattern
export const CORNER_MASKS = {
  TOP_INTERSECTION: 'M56 56V0C56 30.9279 30.9279 56 0 56H56Z',
  LEFT_INTERSECTION: 'M56 56H0C30.9279 56 56 30.9279 56 0V56Z',
} as const

# Design system and motion

Design tokens are declared once in `frontend/src/index.css` (`@theme`) and used through Tailwind classes.

## Colour

| Token | Value | Use |
|---|---|---|
| `primary` | `#5B3A8E` deep plum | primary actions, current selection, brand |
| `accent` | `#E8A317` marigold | highlights on mistakes, stars, focus ring |
| `surface` | `#FFFBF5` | page background |
| `ink`, `ink-muted` | `#2A2420`, `#5E554D` | text |
| `risk-low`, `risk-english-gap`, `risk-support`, `risk-specialist`, `risk-pending` | green, blue, amber, red, grey | risk badges and the class distribution only |

Risk colours never appear alone. Each result shows a coloured mark and its text label, following the 🟢 🔵 🟡 🔴 ⏳ meanings used across Akshar. The page stays in one light theme throughout, because the approved design system is light only.

## Type

- Lexend for headings. It was designed to make reading easier.
- Atkinson Hyperlegible Next for body text.
- Noto Sans Devanagari for Hindi, with a line height of 1.6 or more so matras are never clipped. Child-mode items are shown at 80 to 120 px.

All three are self-hosted through `@fontsource`.

## Components and icons

Icons come from Phosphor (`@phosphor-icons/react`); Unicode symbols and emoji are not used as icons. Cards use a 16 px radius, large panels 20 to 28 px, small controls are pills. Elevation is either a thin border or a soft tinted shadow, not both.

## Motion

Motion uses the Motion library (`motion/react`) and follows the device's reduced-motion setting through `MotionConfig reducedMotion="user"`, plus explicit static fallbacks where a loop would otherwise run.

- Landing page: one authored moment. The hero shows a real reading card listening to a word and then revealing what was heard, with the mistake highlighted and labelled (पमीर → पनीर, मीठा → मिठा, bed → ded). It pauses when scrolled away. Other sections only fade in once.
- Teacher dashboard: the class distribution strip grows once to show how the class splits across results, and clicking a segment filters the table. Filter chips share a sliding highlight, rows animate in and out as the filter changes, and loading shows skeleton rows. Transitions stay between 150 and 450 ms.
- Child mode: the microphone ring follows the child's voice level, each item slides in, and the finish screen bursts stars. None of it shows a score.

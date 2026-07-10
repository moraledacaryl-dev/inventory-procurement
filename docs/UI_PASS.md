# Dedicated UI Pass

This pass focuses only on presentation, navigation, usability, accessibility, and responsive behavior. Business rules and backend workflows are unchanged.

## Visual system

- Consistent Hidden Oasis green brand palette
- Clear canvas, surface, line, text, status, and elevation tokens
- Standard spacing, radius, shadow, typography, form, button, card, and table treatments
- Stronger page hierarchy and reduced visual noise

## Navigation

- Grouped modules: Overview, Inventory, Supply, Production, and Control
- Active route indication
- Compact module icons
- Mobile slide-out navigation with scrim
- Persistent system-status footer
- Keyboard-visible focus states and skip navigation

## Dashboard

- Operational welcome panel
- Direct links to inventory operations and purchasing
- Quick actions for receiving, counts, and system health
- Task-oriented module cards instead of static descriptive cards

## Forms and actions

- Unified field height, borders, focus states, and spacing
- Clear primary and secondary actions
- Better disabled states
- Full-width mobile controls
- Improved feedback and alert presentation

## Data tables

- Framed table component
- Sticky headers
- Stronger header typography
- Row hover states
- Record totals
- Purposeful empty states
- Retained horizontal scrolling on small screens

## Authentication

- Split-screen branded sign-in experience
- Clear application purpose and trust signals
- Loading state during authentication
- Connection-error handling
- Browser autocomplete support

## Responsive behavior

- Desktop sticky sidebar
- Tablet and mobile drawer navigation
- One-column mobile forms and cards
- Responsive dashboard modules
- Reduced mobile padding
- Touch-friendly buttons and controls

## Accessibility

- Semantic navigation and main landmarks
- Skip-to-content link
- Active-page announcement through `aria-current`
- Visible keyboard focus indicators
- Reduced-motion support
- Status and alert roles
- Accessible navigation labels

## Loading experience

A route-level skeleton now provides a consistent transition while Next.js loads pages and route segments.

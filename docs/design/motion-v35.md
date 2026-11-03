# CrashCart motion and landing hierarchy

The workspace serves people investigating payment and delivery problems. Its motion should feel calm and responsive. It must not make evidence appear more certain, animate a result on every poll, or compete with a customer's saved recording.

The existing warm canvas, dark product preview and lime accent remain. The landing introduction is top-aligned on desktop, with less blank space above it. The workspace action, or private access form when signed out, now comes directly after the product description. This keeps the next step ahead of the explanatory links.

Motion uses one corporate easing curve, `cubic-bezier(.2,0,0,1)`, without overshoot. The landing introduction moves 10 pixels over 420 milliseconds; its preview follows after 90 milliseconds over 480 milliseconds. This occurs on document entry, without an observer, scroll listener or persistent loop. Evidence rows and the investigation report remain still during updates.

Opening the saved recording deliberately reveals its panel over 240 milliseconds with a six-pixel movement. Video playback remains user-initiated, with native controls. Buttons move one pixel when pressed and settle over 120 milliseconds. The workspace and recording arrows acknowledge hover or keyboard focus with a two-pixel movement.

All new spatial motion is inside `prefers-reduced-motion: no-preference`. The existing reduced-motion override also disables animations and transitions. On phones, the landing distance drops to six pixels, the primary entrance to 320 milliseconds, the preview to 360 milliseconds and the panel reveal to 180 milliseconds. Motion changes transform and opacity; it does not animate layout dimensions. No continuous ambient animation is used in this financial workflow.

The frontend was implemented directly. No generated design-tool output is claimed.

Verification remains separate from implementation: inspect real desktop and phone layouts, access controls, keyboard focus and playback, plus reduced-motion behavior where browser capability allows. No acceptance requirement is marked verified by this document.

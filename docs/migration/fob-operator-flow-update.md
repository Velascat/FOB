# FOB Operator Flow Update

- `fob providers` now reports selector and lane readiness instead of treating 9router as the provider control plane.
- `fob demo` validates `SwitchBoard /health`, `POST /route`, and the ControlPlane planning handoff.
- Default help text and operator guidance now point to the selector-first architecture only.

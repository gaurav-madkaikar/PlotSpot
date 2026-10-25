# Account and Collections layout implementation

**Goal:** Deliver the requested focused account layout, clean footer/tagline and canonical Collections route.

**Architecture:** Keep existing authentication and collection providers. Relocate explicit visit import to Collections; add a small legacy UI route redirect preserving query/hash.

- [x] Center and simplify account UI, remove aside/import and hide guest-save prompt on Account.
- [x] Replace footer markup/copy and header tagline using existing design tokens.
- [x] Add /collections and query/hash-preserving /collection redirect; update consumer links and safe return destinations.
- [x] Improve Collections heading/toolbar/empty state, remove repeated All saved and relocate explicit guest import.
- [x] Build and run affected browser journeys, inspect live desktop/mobile layouts, and update learning/progress notes.

Validation: frontend build passed. 27 browser journeys passed in the main run; the header-logo locator was made exact to distinguish it from footer branding and its targeted rerun passed. A new sign-in/return/import/persistence journey also passed, for 29 distinct affected journeys. Live account and /collections views were inspected; temporary browser tabs, servers, test configuration and disposable account databases were cleaned up.

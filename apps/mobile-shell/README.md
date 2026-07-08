# SCBKR Mobile Shell

The mobile shell uses the same web product surface through LAN Companion.

Mobile requirements:

- Four bottom navigation targets: Chat, Workbench, Rule Center, Data Center.
- No desktop sidebars on small screens.
- Token Audit and Four-store state remain readable as compact cards.
- Pairing uses a one-time desktop code.
- User signature stays local and explicit.

Implementation target: wrap `apps/web` as a local companion view before native
packaging.

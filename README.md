# Orchestra of Experts

A modular, sequential Mixture-of-Experts architecture.

One small **Conductor** decides which specialist to load. Only one expert is active on the GPU at a time, allowing a huge total model size while staying within consumer hardware limits.

## Core Ideas

- **Conductor**: Always-resident controller that routes tasks and manages expert lifecycle
- **Sequential activation**: Load → Run → Unload one expert at a time
- **Modular experts**: Drop-in GGUF or full models organized in hierarchical folders
- **Community support**: Anyone can add experts under the correct category (naming rules enforced)
- **Hybrid memory**: Inspired by MemPalace (Wings / Rooms / Drawers)

## Folder Structure

```
Orchestra/
├── Conductor/
├── Decision/
├── General/                 # Full models preferred here
├── Maths/
├── Code/
│   ├── General/
│   ├── Python/
│   ├── JavaScript/
│   └── PHP/
├── Literature/
│   ├── Creative/
│   └── Technical/
├── Reasoning/
├── Research/
├── Judge/                   # Only loaded when multiple experts are compared
└── Critic/
```

### Naming Rules for Community Experts

Under any leaf category (e.g. `Code/PHP/`):

- One folder should be named `default` (used when no specific expert is requested)
- All other folders **must contain the category name** in the folder name  
  (e.g. `Bobs_PHP`, `Alices_PHP_Expert`, `PHP_Specialist_v2`)

Invalid names are ignored by the Conductor.

## License

MIT

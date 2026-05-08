# Changelog

All notable changes to this project will be documented here.

---

## [0.1.2] - 2026-05-08

### Fixed
- Claude Desktop config not found on Windows Microsoft Store installs
- WSL path detection now checks Store install path as fallback
- `ModuleNotFoundError: No module named 'mcp'` — added `mcp>=1.0` as dependency

### Added
- `--config-path` option for manual config path override
- Improved error messages showing exactly which paths were checked

---

## [0.1.1] - 2026-05-08

### Changed
- Updated README with cleaner install instructions
- Added package metadata for PyPI (license, keywords, classifiers, URLs)

---

## [0.1.0] - 2026-04-29

### Added
- Initial release
- `mcp setup` — one command to make a codebase AI-ready
- `mcp add`, `remove`, `sync`, `status`, `init`, `unwrap`
- WSL support with automatic path wrapping
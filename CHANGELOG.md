# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Corrected private attribute access in `Renderer.draw_progress()` method
  - Fixed `AttributeError` by replacing `self.layout` with `self._layout`

### Documentation

- Enhanced documentation across multiple modules
- Updated type annotations for better code clarity
- Improved docstrings for `SectionRunner`, `Renderer`, `Navigator`, and utility modules

## [0.0.4] - 2024-11-XX

### Changed

- **BREAKING**: Refactored mouse event handling to use edge detection
  - Prevents accidental double-clicks and improves UI responsiveness
  - Affects `SectionRunner`, `Navigator`, and `Renderer` interaction patterns
- Enhanced method documentation and code organization
- Improved readability in `RavenTask` initialization
- Streamlined UI component setup and window lifecycle management

### Added

- Context manager for PsychoPy window creation and cleanup
- Submit button now shown in practice section
- Custom button labels support

### Fixed

- Option image fill value adjusted for better visual consistency

## [0.0.3] - 2024-11-XX

### Added

- Comprehensive type annotations using TypedDict
  - `Item`, `SectionConfig`, `ParticipantInfo`, `LayoutConfig`, `SequenceConfig`
- Minimal test suite for core modules
  - Tests for `utils`, `models`, `results_writer`
  - Decoupled `SectionTiming` from PsychoPy for testability
- Ruff linter integration for code quality

### Changed

- Improved type safety across all modules
- Enhanced code readability with proper type hints
- Refactored configuration loading with typed returns

### Improved

- Import organization and linting issues
- Indentation inconsistencies

## [0.0.2] - 2024-11-XX

### Added

- `SectionTiming` model for managing section timing state
- `Renderer.show_completion()` for end-of-task screens
- Recording of `remaining_seconds_at_save` in results metadata

### Changed

- Moved `SectionTiming` to `models.py`
- Moved `build_items_from_pattern` to `utils.py`
- Integrated `SectionTiming.remaining_seconds()` into renderer

### Removed

- Unused imports and stale comments
- Legacy code after banner removal

## [0.0.1] - 2024-11-XX

### Added

- Initial release with basic RAPM task implementation
- Practice (Set I) and formal (Set II) sections
- Navigation bar with pagination
- Timer and progress tracking
- Results saving in CSV and JSON formats
- Configurable layout via `configs/layout.json`
- Configurable sequence via `configs/sequence.json`

### Features

- Windowed mode for debugging (`--debug` flag)
- Participant information collection
- Answer modification support
- Auto-advance on timeout
- Memory-optimized rendering with object pooling

---

## Release Notes

### Memory Optimization

All releases include memory-optimized rendering:

- Pre-allocated visual objects (prevents GPU memory leaks)
- Lazy initialization for navigation components
- Object reuse across frames

### Breaking Changes

- **v0.0.4**: Mouse event handling changed to edge detection (affects custom integrations)

### Migration Guide

If upgrading from v0.0.3 or earlier:

1. No code changes required for standard usage
2. Custom mouse handling code may need updates for edge detection pattern
3. All public APIs remain backward compatible

[Unreleased]: https://github.com/EF-STUDY-FENG/rapm-dev/compare/v0.0.4...HEAD
[0.0.4]: https://github.com/EF-STUDY-FENG/rapm-dev/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/EF-STUDY-FENG/rapm-dev/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/EF-STUDY-FENG/rapm-dev/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/EF-STUDY-FENG/rapm-dev/releases/tag/v0.0.1

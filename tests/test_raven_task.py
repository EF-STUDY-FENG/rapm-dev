"""Unit tests for raven_task.py core functionality.

Tests path resolution, config loading, and utility functions without requiring PsychoPy GUI.
"""
import sys
import os
import tempfile
import shutil

# Add scripts to path and mock psychopy before importing raven_task
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Mock psychopy modules to avoid import errors in testing
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['psychopy'] = MockModule()
sys.modules['psychopy.visual'] = MockModule()
sys.modules['psychopy.event'] = MockModule()
sys.modules['psychopy.core'] = MockModule()
sys.modules['psychopy.gui'] = MockModule()
sys.modules['PIL'] = MockModule()
sys.modules['PIL.Image'] = MockModule()

from raven_task import (
    _get_base_dir,
    _get_output_dir,
    _is_stimuli_dir_empty,
    resolve_path,
    file_exists_nonempty,
    load_answers,
)
from config_loader import load_sequence, load_layout


def test_base_dir_exists():
    """Test that base directory can be determined and exists."""
    base_dir = _get_base_dir()
    assert base_dir is not None, "BASE_DIR should not be None"
    assert os.path.isdir(base_dir), f"BASE_DIR should be a directory: {base_dir}"
    print(f"✓ BASE_DIR exists: {base_dir}")


def test_output_dir_exists():
    """Test that output directory can be determined and is writable."""
    output_dir = _get_output_dir()
    assert output_dir is not None, "Output dir should not be None"
    # Output dir might not exist yet, but parent should
    parent = os.path.dirname(output_dir)
    assert os.path.isdir(parent), f"Output dir parent should exist: {parent}"
    print(f"✓ Output dir determined: {output_dir}")


def test_is_stimuli_dir_empty():
    """Test stimuli directory emptiness detection."""
    # Test 1: Non-existent directory should be considered empty
    assert _is_stimuli_dir_empty("/non/existent/path"), "Non-existent dir should be empty"

    # Test 2: Create temp directory with only .gitignore
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore_path = os.path.join(tmpdir, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write("*\n")
        assert _is_stimuli_dir_empty(tmpdir), "Dir with only .gitignore should be empty"

    # Test 3: Create temp directory with actual file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'test.png')
        with open(test_file, 'w') as f:
            f.write("dummy")
        assert not _is_stimuli_dir_empty(tmpdir), "Dir with files should not be empty"

    print("✓ Stimuli directory emptiness detection works correctly")


def test_resolve_path_configs():
    """Test that config files can be resolved."""
    # Test resolving configs directory
    sequence_config = resolve_path('configs/sequence.json')
    layout_config = resolve_path('configs/layout.json')

    # At least one should exist (in dev or bundled)
    assert os.path.exists(sequence_config) or os.path.exists(layout_config), \
        "At least one config file should be resolvable"

    print(f"✓ Config path resolution works")
    if os.path.exists(sequence_config):
        print(f"  - sequence.json: {sequence_config}")
    if os.path.exists(layout_config):
        print(f"  - layout.json: {layout_config}")


def test_file_exists_nonempty():
    """Test file existence and non-emptiness check."""
    # Test with non-existent file
    assert not file_exists_nonempty("/non/existent/file.txt"), \
        "Non-existent file should return False"

    # Test with empty file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        empty_file = f.name
    try:
        assert not file_exists_nonempty(empty_file), "Empty file should return False"
    finally:
        os.unlink(empty_file)

    # Test with non-empty file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("content")
        nonempty_file = f.name
    try:
        assert file_exists_nonempty(nonempty_file), "Non-empty file should return True"
    finally:
        os.unlink(nonempty_file)

    print("✓ file_exists_nonempty() works correctly")


def test_load_answers():
    """Test answer file loading."""
    # Create a temporary answer file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
        f.write("1\n")
        f.write("3\n")
        f.write("\n")  # empty line
        f.write("5\n")
        f.write("invalid\n")  # should be skipped
        f.write("8\n")
        answer_file = f.name

    try:
        answers = load_answers(answer_file)
        assert answers == [1, 3, 5, 8], f"Expected [1, 3, 5, 8], got {answers}"
        print(f"✓ load_answers() works correctly: {answers}")
    finally:
        os.unlink(answer_file)


def test_configs_are_valid_json():
    """Test that config files are valid JSON."""
    import json

    sequence_config = resolve_path('configs/sequence.json')
    layout_config = resolve_path('configs/layout.json')

    configs_tested = 0

    if os.path.exists(sequence_config):
        with open(sequence_config, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert isinstance(data, dict), "sequence.json should be a JSON object"
            assert 'practice' in data or 'formal' in data, \
                "sequence.json should have practice or formal section"
        print(f"✓ sequence.json is valid JSON")
        configs_tested += 1

    if os.path.exists(layout_config):
        with open(layout_config, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert isinstance(data, dict), "layout.json should be a JSON object"
            assert 'font_main' in data, "layout.json should contain font_main key"
        print(f"✓ layout.json is valid JSON & contains font_main")
        configs_tested += 1

    assert configs_tested > 0, "At least one config file should exist and be tested"

def test_separate_config_loader():
    """Test that sequence and layout can be loaded separately."""
    sequence = load_sequence()
    assert 'practice' in sequence and 'formal' in sequence, "sequence config must have practice/formal"
    layout = load_layout()
    assert 'font_main' in layout, "layout config must contain font_main"
    print("✓ separate config loader works")


def test_layout_parameter_merging():
    """Test that layout parameters can be partially overridden."""
    import json
    from config_loader import LAYOUT_DEFAULT_PATH

    # Load default layout to get baseline
    with open(LAYOUT_DEFAULT_PATH, 'r', encoding='utf-8') as f:
        default_layout = json.load(f)

    # Load via function (should be same as default in dev mode)
    loaded_layout = load_layout()

    # Verify all default keys are present
    for key in default_layout:
        assert key in loaded_layout, f"Default key '{key}' should be present in loaded layout"

    # Verify loaded layout has at least the same keys
    assert len(loaded_layout) >= len(default_layout), "Loaded layout should have at least all default keys"

    print("✓ layout parameter merging works (all default keys present)")


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Running Raven Task Unit Tests")
    print("=" * 60)

    tests = [
        test_base_dir_exists,
        test_output_dir_exists,
        test_is_stimuli_dir_empty,
        test_resolve_path_configs,
        test_file_exists_nonempty,
        test_load_answers,
        test_configs_are_valid_json,
        test_separate_config_loader,
        test_layout_parameter_merging,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            print(f"\n[{test_func.__name__}]")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

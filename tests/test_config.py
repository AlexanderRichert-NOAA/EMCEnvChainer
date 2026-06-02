"""Tests for configuration management."""

from emcenvchainer.config import Config


class TestConfig:
    """Test Config class."""

    def test_builtin_platforms(self):
        """Test that all built-in platforms are present with required structural keys."""
        config = Config()
        platforms = config.get_platforms()

        expected_platforms = ["ursa", "orion", "hercules", "jet", "gaea-c5", "gaea-c6", "acorn"]
        for platform in expected_platforms:
            assert platform in platforms
            assert "name" in platforms[platform]
            assert "spack_stack_path" in platforms[platform]
            assert "hostname_patterns" in platforms[platform]
            assert "model_applications" in platforms[platform]

    def test_config_get(self):
        """Test config get() method behavior."""
        config = Config()

        # Missing top-level key returns default
        assert config.get("nonexistent.key", "default") == "default"

        # Missing leaf under a valid intermediate key returns default
        assert config.get("platforms.nonexistent.subkey", "fallback") == "fallback"

        # Nested key access
        assert config.get("platforms.ursa.name") == "Ursa (RDHPCS)"

    def test_platform_configuration(self):
        """Test a representative platform configuration (Ursa)."""
        config = Config()

        ursa_config = config.get("platforms.ursa")
        assert ursa_config["name"] == "Ursa (RDHPCS)"
        assert "hostname_patterns" in ursa_config

        model_apps = ursa_config["model_applications"]
        assert "ufs_weather_model" in model_apps
        assert "global_workflow" in model_apps

    def test_applications_configuration(self):
        """Test that all shared application configurations are present with required fields."""
        config = Config()
        applications = config.get_applications()

        expected_apps = [
            "ufs_weather_model", "global_workflow", "gsi", "upp",
            "ufs_utils", "aqm_utils", "rrfs_nco", "rrfs_dev_sci",
        ]
        for app in expected_apps:
            assert app in applications, f"Application '{app}' missing from config"
            assert "name" in applications[app], f"Application '{app}' missing 'name'"
            assert "install_path_regex" in applications[app], f"Application '{app}' missing 'install_path_regex'"

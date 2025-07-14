"""Built-in configuration for emcenvchainer."""

from typing import Dict, List, Optional


class Config:
    """Built-in configuration for emcenvchainer."""
    
    def __init__(self):
        """Initialize with built-in configuration."""
        self._config = self._get_builtin_config()
    
    def _get_builtin_config(self) -> Dict:
        """Get built-in configuration."""
        return {
            "spack_repository": {
                "base_url": "https://github.com/JCSDA/spack.git",
                "packages_path": "var/spack/repos/builtin/packages",
                "custom_repo_name": "envrepo",
                "branch": "spack-stack-dev"
            },
            "platforms": {
                "ursa": {
                    "name": "Ursa (RDHPCS)",
                    "spack_stack_path": "/contrib/spack-stack",
                    "detection_paths": ["/tmp_mnt/ursa"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                        }
                    }
                },
                "hera": {
                    "name": "NOAA Hera",
                    "spack_stack_path": "/tmp/spack-stack",
                    "detection_paths": ["/xxxtmp", "/xxxvar"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hera.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hera.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)"\)'
                        }
                    }
                },
                "orion": {
                    "name": "NOAA Orion", 
                    "spack_stack_path": "/work/noaa/epic/role-epic/spack-stack",
                    "detection_paths": ["/work", "/work2"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/orion.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/orion.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                        }
                    }
                },
                "hercules": {
                    "name": "NOAA Hercules",
                    "spack_stack_path": "/work/noaa/epic/role-epic/spack-stack", 
                    "detection_paths": ["/work", "/work2"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/hercules.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/hercules.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                        }
                    }
                },
                "derecho": {
                    "name": "NCAR Derecho",
                    "spack_stack_path": "/glade/work/epicufsrt/contrib/spack-stack",
                    "detection_paths": ["/glade/work", "/glade/u"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/derecho.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/derecho.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                        }
                    }
                },
                "jet": {
                    "name": "NOAA Jet",
                    "spack_stack_path": "/lfs4/HFIP/hfv3gfs/role.epic/spack-stack",
                    "detection_paths": ["/lfs4", "/mnt/lfs4"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/jet.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/jet.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                        }
                    }
                },
                "gaea": {
                    "name": "NOAA Gaea",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack",
                    "detection_paths": ["/ncrc/proj", "/ncrc/home"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/gaea.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/gaea.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                        }
                    }
                }
            },
            "spack": {
                "custom_repo_name": "emcenvchainer-custom",
                "environment_prefix": "emcenv-"
            },
            "ui": {
                "theme": "default",
                "show_help": True
            }
        }
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value):
        """Set configuration value."""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def get_platforms(self) -> Dict:
        """Get platform configurations."""
        return self.get("platforms", {})

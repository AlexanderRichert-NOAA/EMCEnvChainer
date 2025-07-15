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
                    "cpu_target": "zen3",
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                        }
                    }
                },
                "orion": {
                    "name": "Orion (RDHPCS/MSU)", 
                    "spack_stack_path": "/work/noaa/epic/role-epic/spack-stack",
                    "detection_paths": ["/work", "/scratch/orion"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_orion.intelllvm.lua",
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
                "hercules": {
                    "name": "Hercules (RDHPCS/MSU)",
                    "spack_stack_path": "/work/noaa/epic/role-epic/spack-stack", 
                    "detection_paths": ["/work", "/scratch/hercules"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hercules.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hercules.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
                "derecho": {
                    "name": "Derecho (NCAR)",
                    "spack_stack_path": "/glade/work/epicufsrt/contrib/spack-stack/derecho",
                    "detection_paths": ["/glade/work", "/glade/u"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_derecho.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_derecho.gnu.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
                "jet": {
                    "name": "Jet (RDHPCS)",
                    "spack_stack_path": "/lfs4/HFIP/hfv3gfs/role.epic/spack-stack",
                    "detection_paths": ["/lfs4", "/mnt/lfs4"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_jet.intel.lua",
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
                "gaea-c5": {
                    "name": "Gaea C5 (NOAA)",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack/c5",
                    "detection_paths": ["/ncrc", "/gpfs/f5"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac5.intelllvm.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
                "gaea-c6": {
                    "name": "Gaea C6 (NOAA)",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack/c6",
                    "detection_paths": ["/ncrc", "/gpfs/f6"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "name": "UFS Weather Model",
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac6.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac6.intelllvm.lua"
                            ],
                            "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                            "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'                        }
                    }
                },
            },
            "spack": {
                "custom_repo_name": "emcenvchainer-custom",
                "environment_prefix": "emcenv-"
            },
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

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
            "applications": {
                "ufs_weather_model": {
                    "name": "UFS Weather Model",
                    "spack_metapackage": "ufs-weather-model-env",
                    "common_module_url": "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_common.lua",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "global_workflow": {
                    "name": "Global Workflow",
                    "spack_metapackage": "global-workflow-env",
                    "package_versions_url": "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/versions/spack.ver",
                    "package_versions_format": "shell_exports",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                }
            },
            "platforms": {
                "ursa": {
                    "name": "Ursa (RDHPCS)",
                    "spack_stack_path": "/contrib/spack-stack",
                    "hostname_patterns": ["ufe0[1-4]-cluster.+", "uecflow01-cluster.+"],
                    "cpu_target": "zen3",
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_ursa.gnu.lua"
                            ]
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.ursa.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_run.ursa.lua"
                            ]
                        }
                    }
                },
                "orion": {
                    "name": "Orion (RDHPCS/MSU)", 
                    "spack_stack_path": "/apps/contrib/spack-stack",
                    "hostname_patterns": [r"Orion-login.*\.HPC.MsState.Edu"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_orion.intelllvm.lua",
                            ],
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.orion.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_run.orion.lua"
                            ]
                        }
                    }
                },
                "hercules": {
                    "name": "Hercules (RDHPCS/MSU)",
                    "spack_stack_path": "/apps/contrib/spack-stack", 
                    "hostname_patterns": [r"Hercules-login.*\.HPC.MsState.Edu"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hercules.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_hercules.gnu.lua"
                            ]
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.hercules.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_run.hercules.lua"
                            ]
                        }
                    }
                },
                "jet": {
                    "name": "Jet (RDHPCS)",
                    "spack_stack_path": "/lfs4/HFIP/hfv3gfs/role.epic/spack-stack",
                    "hostname_patterns": [".+.jet.boulder.rdhpcs.noaa.gov"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_jet.intel.lua",
                            ],
                        }
                    }
                },
                "gaea-c5": {
                    "name": "Gaea C5 (NCRC/NOAA)",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack/c5",
                    "hostname_patterns": ["gaea5[1-8].ncrc.gov"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac5.intel.lua"
                            ]
                        }
                    }
                },
                "gaea-c6": {
                    "name": "Gaea C6 (NCRC/NOAA)",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack/c6",
                    "hostname_patterns": ["gaea6[0-8].ncrc.gov"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac6.intel.lua",
                            ]
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.gaeac6.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_run.gaeac6.lua"
                            ]
                        }
                    }
                },
                "acorn": {
                    "name": "Acorn (NOAA)",
                    "spack_stack_path": "/lfs/h1/emc/nceplibs/noscrub/spack-stack",
                    "hostname_patterns": ["a.*.wcoss2.ncep.noaa.gov"],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_acorn.intel.lua",
                            ]
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.wcoss2.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_run.wcoss2.lua"
                            ]
                        }
                    }
                },
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
    
    def get_platforms(self) -> Dict:
        """Get platform configurations."""
        return self.get("platforms", {})

    def get_applications(self) -> Dict:
        """Get application configurations."""
        return self.get("applications", {})

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
                },
                "gsi": {
                    "name": "GSI",
                    "spack_metapackage": "gsi-env",
                    "common_module_url": "https://raw.githubusercontent.com/NOAA-EMC/GSI/develop/modulefiles/gsi_common.lua",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "upp": {
                    "name": "UPP",
                    "common_module_url": "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/upp_common.lua",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "ufs_utils": {
                    "name": "UFS_UTILS",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "aqm_utils": {
                    "name": "AQM-utils",
                    "common_module_url": "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_common.lua",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "rrfs_nco": {
                    "name": "RRFS (rrfs-nco)",
                    "common_module_url": "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/rrfs-nco/modulefiles/rrfs_common.lua",
                    "install_path_regex": r'prepend_path\("MODULEPATH",\s*"([^"]+)modulefiles/Core.?"\)'
                },
                "rrfs_dev_sci": {
                    "name": "RRFS (dev-sci)",
                    "common_module_url": "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/rrfs_common.lua",
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
                            ]
                        },
                        "gsi": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/GSI/develop/modulefiles/gsi_ursa.intel.lua"
                            ]
                        },
                        "upp": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/ursa_intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/ursa_intelllvm.lua"
                            ]
                        },
                        "ufs_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.ursa.intelllvm.lua",
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.ursa.gnu.lua"
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_ursa.intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_ursa.intelllvm.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_ursa.gnu.lua"
                            ]
                        }
                    }
                },
                "orion": {
                    "name": "Orion (RDHPCS/MSU)", 
                    "spack_stack_path": "/apps/contrib/spack-stack",
                    "hostname_patterns": [r"Orion-login.*\.HPC.MsState.Edu"],
                    "metamodule_patches": [
                        {
                            "pattern": r'load\("spack-managed-x86-64_v3"\)',
                            "replacement": 'prepend_path("MODULEPATH", "/apps/spack-managed-x86_64_v3-v1.0/modulefiles/Core:/apps/other/modulefiles:/apps/containers/modulefiles:/apps/licensed/modulefiles")'
                        },
                        {
                            "pattern": r'prereq\("spack-managed-x86-64_v3"\)',
                            "replacement": ""
                        }
                    ],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_orion.intelllvm.lua",
                            ],
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.orion.lua",
                            ]
                        },
                        "gsi": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/GSI/develop/modulefiles/gsi_orion.intel.lua"
                            ]
                        },
                        "upp": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/orion_intel.lua"
                            ]
                        },
                        "ufs_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.orion.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.orion.intelllvm.lua"
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_orion.intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_orion.intelllvm.lua"
                            ]
                        },
                        "rrfs_nco": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/rrfs-nco/modulefiles/wflow_orion.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_orion.lua"
                            ]
                        }
                    }
                },
                "hercules": {
                    "name": "Hercules (RDHPCS/MSU)",
                    "spack_stack_path": "/apps/contrib/spack-stack", 
                    "hostname_patterns": [r"Hercules-login.*\.HPC.MsState.Edu"],
                    "metamodule_patches": [
                        {
                            "pattern": r'load\("spack-managed-x86-64_v3"\)',
                            "replacement": 'prepend_path("MODULEPATH", "/apps/spack-managed-x86_64_v3-v1.0/modulefiles/Core:/apps/other/modulefiles:/apps/containers/modulefiles:/apps/licensed/modulefiles")'
                        },
                        {
                            "pattern": r'prereq("spack-managed-x86-64_v3")',
                            "replacement": ""
                        }
                    ],
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
                            ]
                        },
                        "gsi": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/GSI/develop/modulefiles/gsi_hercules.intel.lua"
                            ]
                        },
                        "upp": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/hercules_intel.lua"
                            ]
                        },
                        "ufs_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.hercules.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.hercules.intelllvm.lua"
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_hercules.intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_hercules.intelllvm.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_hercules.gnu.lua"
                            ]
                        },
                        "rrfs_nco": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/rrfs-nco/modulefiles/wflow_hercules.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_hercules.lua"
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
                        },
                        "upp": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/jet_intel.lua"
                            ]
                        },
                        "ufs_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.jet.intel.lua",
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.jet.intelllvm.lua"
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_jet.intel.lua"
                            ]
                        },
                        "rrfs_nco": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/rrfs-nco/modulefiles/wflow_jet.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_jet.lua"
                            ]
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
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_gaeac5.intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_gaeac5.intelllvm.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_gaea.lua"
                            ]
                        }
                    }
                },
                "gaea-c6": {
                    "name": "Gaea C6 (NCRC/NOAA)",
                    "spack_stack_path": "/ncrc/proj/epic/spack-stack/c6",
                    "hostname_patterns": ["gaea6[0-8].ncrc.gov"],
                    "spack_stack_path_overrides": [
                        {"old": "/ncrc/proj/epic/spack-stack/c6/spack-stack-1.9.2/envs/ue-intel-2023.2.0", "new": "/ncrc/proj/epic/spack-stack/c6/spack-stack-1.9.2/envs/ue-intel-2023.2.0-new"}
                    ],
                    "model_applications": {
                        "ufs_weather_model": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/ufs-weather-model/develop/modulefiles/ufs_gaeac6.intel.lua",
                            ]
                        },
                        "global_workflow": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/global-workflow/develop/modulefiles/gw_setup.gaeac6.lua",
                            ]
                        },
                        "gsi": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/GSI/develop/modulefiles/gsi_gaeac6.intel.lua"
                            ]
                        },
                        "upp": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/UPP/develop/modulefiles/gaeac6_intel.lua"
                            ]
                        },
                        "ufs_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/ufs-community/UFS_UTILS/develop/modulefiles/build.gaeac6.intel.lua"
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_gaeac6.intel.lua",
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_gaeac6.intelllvm.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_gaea.lua"
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
                            ]
                        },
                        "aqm_utils": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/AQM-utils/develop/modulefiles/aqm-utils_acorn.intel.lua"
                            ]
                        },
                        "rrfs_nco": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/rrfs-nco/modulefiles/wflow_wcoss2.lua"
                            ]
                        },
                        "rrfs_dev_sci": {
                            "module_url_templates": [
                                "https://raw.githubusercontent.com/NOAA-EMC/rrfs-workflow/dev-sci/modulefiles/wflow_wcoss2.lua"
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

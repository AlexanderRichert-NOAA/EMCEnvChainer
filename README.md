# EMCEnvChainer

![unit tests](https://github.com/AlexanderRichert-NOAA/EMCEnvChainer/actions/workflows/unit-tests.yml/badge.svg)

The EMCEnvChainer utility allows NOAA developers to build their own copies of packages (i.e., model app dependencies) on top of existing spack-stack installations. It does so using Spack's environment chaining feature. Only the specifically requested package(s) and corresponding dependents need to be rebuilt, therefore as much of the existing installation as possible is reused, thereby reducing overall installation time and minimizing configuration differences (versions, build options) between the base (upstream) and user-built software stacks.

The utility will automatically identify which platform (RDHPCS systems + Acorn) it is running on, and identify available base spack-stack installations, including the ones associated with supported model applications at the head of their respective default branches (i.e., "develop").

## Installation & basic usage

To use the utility, install it, invoke the `emcenvchainer` command, and follow the prompts:
```console
pip3 install emcenvchainer
emcenvchainer
```
You may choose a spack-stack installation and select individual packages to incorporate into your installation, or you may choose a model application to automatically obtain the list of dependencies based on the head of its default branch, then choose whether to customize the version/build options for each. The model applications currently supported are: UFS Weather Model, Global Workflow, GSI, UPP, UFS_UTILS, and AQM-utils. After the installation is complete, instructions are provided for accessing the stack.

> [!NOTE]
> **The Lmod module files and spack-stack metamodules for accessing the base and user packages are installed in a single location** in the user's space. Therefore, when setting `$MODULEPATH` for your application, it should *not* include the original spack-stack installation, only the one associated with the newly built Spack environment.

To override the automatic platform detection, export the `$SITE_OVERRIDE` environment variable:
```console
SITE_OVERRIDE=ursa emcenvchainer
```

> [!IMPORTANT]
> Compatibility for xterm must be enabled in your terminal (PuTTY, Tectia/sshg3, SecureCRT) or the utility will immediately fail with an error.

## Add'l usage & troubleshooting

### *Spack won't use some of the existing packages*

Occasionally Spack will not use existing packages from the upstream environment even when it ostensibly should. For instance, the concretization output may show that it intends to perform a fresh build of HDF5 and its dependents even though we are only requesting a new version of Scotch, which is not in any way a dependency or dependent of HDF5. There are deep internal Spack reasons for this, usually related to spuriously differing package hashes or obscure concretizer errors.

This problem can be straightforwardly worked around if you are using the model app-based approach to configuring your installation. On the package selection screen, packages may be **locked** to their existing upstream spec, that is, Spack will be forced to point to the upstream package rather than reconfiguring and rebuilding it. To lock the a package, highlight it and press `l`; the package label will update to show a 🔒 indicator with the spec and hash being used. Press `l` again to cycle to subsequent available upstream specs if there is more than one, and pressing 'l' again after that will unlock the package. To lock all packages to their first available upstream spec, press `L`, then use `l` to unlock only those packages you wish to allow Spack to reconfigure and rebuild.

There is little risk to locking any and all packages, as long as they are not packages that need building (i.e., package versions you have requested or dependents of packages you have selected to reconfigure). If locking packages leads to hard conflicts, the concretization will fail.

### *I want to modify the Spack environment before installing*

The utility can be halted at any time using Ctrl-c. At any time after the Spack environment configuration has been written (spack.yaml+various other files), you may stop the utility, activate the environment by sourcing `activate_spack_env.sh`, and modify the environment before running `spack install`. For example, to add a new package constraint:
```console
$ cd <Spack env directory>
$ . activate_spack_env.sh
$ spack config add 'packages:hdf5:require:+szip' # or manually edit config files
$ spack concretize
$ spack install
```

### *I want to install additional packages*

At any point after the Spack environment configuration (spack.yaml+various other files) has been written, you may modify the environment, including to add more packages. The simplest approach is to add new packages after the initial installation is complete. For example, if you have already run an installation based on the UFS Weather Model dependencies, the following steps can be used to add the MET and METplus packages:
```console
$ cd <Spack env directory>
$ . activate_spack_env.sh
$ spack install --add met metplus
# if modules have not already been automatically generated:
$ spack module lmod refresh
```

### *I'm getting angry emails from sys admins for running large builds on login nodes*

This utility does not currently support building under batch schedulers (SLURM, PBS Pro, etc.). To avoid angry emails, such as on the MSU systems (Orion & Hercules):
 1. On a login node: Run the utility until after the concretization step but before initiating the installation itself (i.e., Ctrl-c when the concretization output is displayed).
 2. On a login node: Activate the Spack environment (`. activate_spack_env.sh`) and run `spack fetch --missing` to retrieve source code for the packages to be built.
 3. On a compute node: Run `spack install`. To run via interactive job on a compute node, first source `activate_spack_env.sh`.
With SLURM (RDHPCS machines):
```console
srun --account=myacctname --partition=dev --time=01:00:00 --nodes=1 --cpus-per-task=6 --pty --export=ALL $(which spack) install -p1 -j6
```
With PBS Pro (Acorn):
```console
qsub -A MYACCT-DEV -q dev -l walltime=01:00:00,select=1:ncpus=6 -I -V -- $(which spack) install -p1 -j6
```

### *I want to make my own source code modifications to one or more packages*

On the "Package Specification" screen for any package, you can check the **"Develop with persistent source code directory ('spack develop')"** checkbox. This will automatically run `spack develop` for the package after the environment is configured, creating a local source directory that you can modify before building.

See the [Spack documentation](https://spack-tutorial.readthedocs.io/en/latest/tutorial_developer_workflows.html#development-iteration-cycles) for details on iterative code development through the use of `spack develop`.

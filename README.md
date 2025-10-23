# EMCEnvChainer

![unit tests](https://github.com/AlexanderRichert-NOAA/EMCEnvChainer/actions/workflows/unit-tests.yml/badge.svg)

The EMCEnvChainer utility allows NOAA developers to build their own copies of packages (i.e., model app dependencies) on top of existing spack-stack installations. It does so using Spack's environment chaining feature. Only the specifically requested package(s) and corresponding dependents need to be rebuilt, therefore as much of the existing installation as possible is reused, thereby reducing overall installation time and minimizing configuration differences (versions, build options) between the base and user software stacks.

To use the utility, install it, invoke the `emcenvchainer` command, and follow the prompts:
```console
pip3 install emcenvchainer
emcenvchainer
```

> [!NOTE]
> This utility relies on Spack's built-in environment chaining capabilities. The ability to chain environments with Spack/spack-stack in some circumstances depends on using the same Python version/installation as the one that generated the main spack-stack installation. The Python versions/installations used to install spack-stack on each platform are not particularly well documented or consistent. If you find that Spack does not reuse existing packages from the base installation in cases where it should, please reach out to the [spack-stack maintainers for your HPC platform]([url](https://spack-stack.readthedocs.io/en/latest/PreConfiguredSites.html)) (typically EPIC) or [create a spack-stack issue]([url](https://github.com/JCSDA/spack-stack/issues/new/choose)).

To override the automatic platform detection, export the SITE_OVERRIDE environment variable:
```console
SITE_OVERRIDE=ursa emcenvchainer
```

> [!IMPORTANT]
> xterm support must be enabled (such as for PuTTY, Tectia/sshg3, SecureCRT) or the utility will immediately fail with an error.

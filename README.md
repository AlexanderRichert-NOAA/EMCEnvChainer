# EMCEnvChainer

This is a utility for quickly adding packages to existing spack-stack environments using Spack's environment chaining feature.

To install and run the utility:
```console
pip3 install emcenvchainer
emcenvchainer
```

To override the automatic platform detection, set the SITE_OVERRIDE environment variable:
```console
SITE_OVERRIDE=ursa
```

NOTE: When using the Tectia/sshg3 client, xterm support must be enabled or the utility will immediately fail with an error.

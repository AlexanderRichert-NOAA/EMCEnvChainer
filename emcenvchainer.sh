#!/bin/bash

set -e

# Eventually: select application

# Select platform
echo "Select a platform. For a list of platforms supported,"
echo "see https://github.com/ufs-community/ufs-weather-model/tree/develop/modulefiles"
read -rp "Platform (hera, hercules, etc.): " PLATFORM
echo "Selected platform '${PLATFORM:?}'"

# Select compiler
echo "Select 'intel' 'gnu' or 'intelllvm' depending on what is available on your system."
read -rp "Compiler: " COMPILER
echo "Selected compiler '${COMPILER:?}'"

# Select env name
echo 'Set a name for your Spack environment. Default is $USER-$(date +%y%m%d).'
read -rp "Environment name: " ENVNAME
ENVNAME=${ENVNAME:-$(echo $USER-$(date +%y%m%d))}

# Select packages
echo "Enter Spack package specs to be tested."
echo "Remember, pio is 'parallelio', grib_util is 'grib-util', prod_util is 'prod-util', wrf_io is 'wrf-io', ufs_utils is 'ufs-utils'."
echo "Examples:"
echo "  esmf@8.6.1"
echo "  esmf@8.6.1 +debug"
echo "  esmf@8.6.1 mapl@2.40.3.1"
read -rp "Specs: " PKGSPECS
echo "Selected specs: ${PKGSPECS:?}"

# Get Spack
mkdir -p tmp
cd tmp
echo "Getting UWM modulefile for $PLATFORM/$COMPILER..."
wget https://raw.githubusercontent.com/ufs-community/ufs-weather-model/refs/heads/develop/modulefiles/ufs_$PLATFORM.$COMPILER.lua &> /dev/null
current_modulepath=$(grep -oP 'prepend_path\("MODULEPATH",\s*"\K[^"]+' ufs_$PLATFORM.$COMPILER.lua)
spackstackversion=$(echo $current_modulepath | grep -oP '/spack-stack-\K[\d\.]+(?=/)')
wget https://raw.githubusercontent.com/ufs-community/ufs-weather-model/refs/heads/develop/modulefiles/ufs_common.lua &> /dev/null
uwm_packages=$(grep -oP '{\["\K[^"]+' ufs_common.lua)
cd ..

if [ ! -d spack-stack-${spackstackversion} ]; then
  echo "Cloning spack-stack-${spackstackversion}..."
  if [ ${spackstackversion} == 1.6.0 ]; then
    git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/AlexanderRichert-NOAA/spack-stack -b multichain-1.6.0 spack-stack-$spackstackversion &> /dev/null
  else
    git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/JCSDA/spack-stack -b release/$spackstackversion spack-stack-$spackstackversion &> /dev/null
  fi
fi

if [[ ! " 1.5 1.6 " =~ " ${spackstackversion:0:3} " ]]; then
  compilersetting="--compiler=${COMPILER/intelllvm/oneapi}"
fi

cd spack-stack-$spackstackversion
. setup.sh

if [ ! -z "$addpkglist" ]; then
  modargs=$(echo " $addpkglist" | sed 's| | --modify-pkg=|g')
fi

# Create env
upstream_path=$(echo $current_modulepath | grep -oP "^.+(?=modulefiles/Core)")
spack stack create env $compilersetting \
  --name $ENVNAME \
  --template empty \
  --site ${PLATFORM/gaea/gaea-c5} \
  --upstream $upstream_path

cd envs/$ENVNAME
spack env activate .
spack add ufs-weather-model-env ~python
spack add $PKGSPECS

if [[ " 1.5 1.6 1.7 " =~ " ${spackstackversion:0:3} " ]]; then
  sed -i 's|fms@[^"]\+|fms|' $(spack location --package-dir ufs-weather-model-env)/package.py
fi

first_upstream=$(spack config get 'upstreams' | grep -m1 -oP "install_tree: \K.+")

for part in $PKGSPECS; do
  if [ $(echo $part | grep -Pc "[-\w]+@[-\.\w]+") -eq 1 ]; then
    pkg=${part%@*}
    version=${part#*@}
    EDITOR=echo spack checksum --add-to-package $pkg $version
    spack config add "packages:$pkg:require:'@$version'"
    variants=$(spack --env $(dirname $first_upstream) find --format '{variants} {compiler_flags}' $pkg%$COMPILER | sed "s|\"|'|g;s|snapshot=[^ ]\+||")
    spack config add "packages:$pkg:variants:'$variants'"
  fi
done

while true; do
  echo "Any new versions needed should already have been automatically added to each package's recipe."
  read -rp "Enter the name of a package (e.g., 'esmf', 'parallelio') to further edit with \$EDITOR, or press ENTER to continue: " pkgtoedit
  if [ -z $pkgtoedit ]; then
    break
  else
    spack edit $pkgtoedit
    unset pkgtoedit
  fi
done

# Concretize
echo "Concretizing, then installing. No more input is needed, you may leave this script unattended."
echo "If you don't see any '[^]' at the beginning of some/most lines in the concretization output,"
echo "it means the upstream environment(s) could not be found and used. Any package where the "
echo "output starts with ' -  ' is one that will be compiled as opposed to using an existing copy."
spack concretize | tee log.concretize
${SPACK_STACK_DIR}/util/show_duplicate_packages.py -d log.concretize

# Install
spack install --fail-fast

# Modules
# Make sure 'mapl' modulefile name is set properly according to 'esmf' spec:
echo "Generating module files"
esmfmatch=$(spack find --format '{name}@{version} {variants.snapshot}' esmf)
maplsuffix=$(spack find --format '{name}-{version}' esmf)
spack config add "modules:default:lmod:mapl:suffixes:^$esmfmatch:'$maplsuffix'"
spack module lmod refresh --upstream-modules --yes-to-all &> log.lmodrefresh
spack stack setup-meta-modules &> log.setupmetamodules

# Spit out path for $MODULEPATH
echo
echo "##################################################################"
echo "Fingers crossed, this installation has completely successfully."
echo 'Use the following path in your $MODULEPATH variable *in place of* the existing path.'
echo "    $SPACK_ENV/install/modulefiles/Core"
echo "You may use the following environment variables to override the default versions in ufs_common.lua:"
spack find --format 'export {name}_ver={version}' $uwm_packages | sed "s|-|_|g;s|^|    |;s|mapl_ver=.*|\0-$maplsuffix|"

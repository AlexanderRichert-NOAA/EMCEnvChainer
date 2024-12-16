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
mkdir tmp
cd tmp
echo "Getting UWM modulefile for $PLATFORM/$COMPILER..."
wget https://raw.githubusercontent.com/ufs-community/ufs-weather-model/refs/heads/develop/modulefiles/ufs_$PLATFORM.$COMPILER.lua &> /dev/null
current_modulepath=$(grep -oP 'prepend_path\("MODULEPATH",\s*"\K[^"]+' ufs_$PLATFORM.$COMPILER.lua)
spackstackversion=$(echo $current_modulepath | grep -oP '/spack-stack-\K[\d\.]+(?=/)')
cd ..

echo "Cloning spack-stack@${spackstackversion}..."
if [ ${spackstackversion} == 1.6.0 ]; then
  git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/AlexanderRichert-NOAA/spack-stack -b multichain-1.6.0 &> /dev/null
else
  git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/JCSDA/spack-stack -b release/$spackstackversion &> /dev/null
fi

if [[ ! " 1.5 1.6 " =~ " ${spackstackversion:0:3} " ]]; then
  compilersetting="--compiler=${COMPILER/intelllvm/oneapi}"
fi

cd spack-stack
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

for part in $PKGSPECS; do
  if [ $(echo $part | grep -Pc "[-\w]+@[-\.\w]+") -eq 1 ]; then
    pkg=${part%@*}
    version=${part#*@}
    EDITOR=echo spack checksum --add-to-package $pkg $version
    spack config add "packages:$pkg:require:'@$version'"
  fi
done

while true; do
  read -rp "Enter the name of a package (e.g., 'esmf', 'parallelio') to edit with \$EDITOR ($EDITOR), or press ENTER to continue: " pkgtoedit
  if [ -z $pkgtoedit ]; then
    break
  else
    spack edit $pkgtoedit
    unset pkgtoedit
  fi
done

# Concretize
spack concretize | tee log.concretize
${SPACK_STACK_DIR}/util/show_duplicate_packages.py -d log.concretize

# Install
spack install --fail-fast

# Modules
spack module lmod refresh --upstream-modules --yes-to-all
spack stack setup-meta-modules

# Spit out path for $MODULEPATH
echo
echo "Fingers crossed, this installation has completely successfully."
echo 'Use the following path in your $MODULEPATH variable *in place of* the existing path.'
echo "    $SPACK_ENV/install/modulefiles/Core"

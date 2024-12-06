#!/bin/bash

# Eventually: select application

# Select platform
echo "Select a platform. For a list of platforms supported,"
echo "see https://github.com/ufs-community/ufs-weather-model/tree/develop/modulefiles"
read -rp "Platform (hera, hercules, etc.): " PLATFORM

# Select compiler
echo "Select 'intel' 'gnu' or 'intelllvm' depending on what is available on your system."
read -rp "Compiler: " COMPILER

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

# Get Spack
mkdir tmp
cd tmp
wget https://raw.githubusercontent.com/ufs-community/ufs-weather-model/refs/heads/develop/modulefiles/ufs_$PLATFORM.$COMPILER.lua
current_modulepath=$(grep -oP 'prepend_path\("MODULEPATH",\s*"\K[^"]+' ufs_$PLATFORM.$COMPILER.lua)
spackstackversion=$(echo $current_modulepath | grep -oP '/spack-stack-\K[\d\.]+(?=/)')
git clone --recurse-submodules https://github.com/JCSDA/spack-stack -b release/$spackstackversion
cd spack-stack
wget https://raw.githubusercontent.com/JCSDA/spack-stack/d52aec5f089d75dbddbddbf7b6f61f740396794a/spack-ext/lib/jcsda-emc/spack-stack/stack/stack_env.py -O spack-ext/lib/jcsda-emc/spack-stack/stack/stack_env.py
. setup.sh

if [[ ! " 1.5 1.6 " =~ " ${spackstackversion:0:3} " ]]; then
  compilersetting="--compiler=$COMPILER"
fi

for part in $PKGSPECS; do
  if [ $(grep -Pc "[-\w]+@[-\.\w]+") -eq 1 ]; then
    spack config add "repos:[$env/envrepo]"
    pkg=${part%@*}
    version=${part#*@}
    if [[ ! " $(spack version --safe $pkg) " =~ " $version " ]]; then
       addpkglist+=" $pkg"
       addspeclist+=" $part"
    fi
  fi
done

if [ ! -z "$addpkglist" ]; then
  modargs=$(echo $addpkglist | sed 's| | --modify-pkg=|g')
fi

# Create env
upstream_path=$(echo $current_modulepath | grep -oP "^.+(?=modulefiles/Core)")
spack stack create env $compilersetting $modargs \
  --name $ENVNAME \
  --template empty \
  --site $PLATFORM \
  --upstream $upstream_path

cd envs/$ENVNAME
spack env activate .
spack add ufs-weather-model-env
spack add $PKGSPECS

for spec in $addspeclist; do
  EDITOR=echo spack checksum --add-to-package ${spec%@*} ${spec#*@}
done

# Concretize
spack concretize | tee log.concretize
../../util/show_duplicate_package.py -d log.concretize

# Install
spack install

# Modules
spack module lmod refresh --upstream-modules
spack stack setup-meta-modules

# Spit out path for $MODULEPATH
echo "Fingers crossed, this installation has completely successfully."
echo 'Use the following path in your $MODULEPATH variable *in place of* the existing path.'
echo $SPACK_ENV/install/modulefiles/Core

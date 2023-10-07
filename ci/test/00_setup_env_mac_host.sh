#!/usr/bin/env bash
#
# Copyright (c) 2019-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

export LC_ALL=C.UTF-8

export HOST="x86_64-apple-darwin22.4.0"
export PIP_PACKAGES="zmq"
export GOAL="install"
export BOOST_PREFIX=$(brew --prefix boost)
export BITCOIN_CONFIG="--with-gui --enable-reduce-exports --with-boost-process --with-boost='${BOOST_PREFIX}'"
export CI_OS_NAME="macos"
export NO_DEPENDS=1
export OSX_SDK=""
export CCACHE_SIZE=300M

# FIXME: security checks have to be disabled
#        until contrib/devtools/*-check.py supports arm64-darwin
export RUN_SECURITY_TESTS="false"

# Compiler for Mac native warns on C99 in dependencies.
export NO_WERROR=1

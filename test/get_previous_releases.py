#!/usr/bin/env python3
#
# Copyright (c) 2018-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
#
# Download or build previous releases.
# Needs curl and tar to download a release, or the build dependencies when
# building a release.

import argparse
import contextlib
from fnmatch import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import hashlib

DEFAULT_BINARY_URL = "https://archive.dogecoincore.org"

SHA256_SUMS = {

  "fae35ef220ab09c449e9213b966df2bc234aa76d936f5205e6d4bf03a1c47e7e": "dogecoin-1.14.0-aarch64-linux-gnu.tar.gz",
  "db7858a949015be2dbff238ae7da2ae9ea86c804dcba6f5768cd6bcce07fd8be": "dogecoin-1.14.0-arm-linux-gnueabihf.tar.gz",
  "323ec725a885fcc479676f6e48c676e6d81f7146e5ec4816cad99d4522f46164": "dogecoin-1.14.0-i686-pc-linux-gnu.tar.gz",
  "ed7baccafab98b5ce452bd3fd2cf7ab5e757269105350283e2bab91e4ccb7366": "dogecoin-1.14.0-x86_64-linux-gnu.tar.gz",

  "b80bd2b55b67f218efde9498af18581244105c258e7790f7166df1afa1a89f1d": "dogecoin-1.14.2-aarch64-linux-gnu.tar.gz",
  "60c3aac0c336dcc227a217b62571ed76c892cc37d0d08d0e07cd119344d00360": "dogecoin-1.14.2-arm-linux-gnueabihf.tar.gz",
  "6bdcfcbad88c0d9dfca180b8801f7d02e3ebf053b8657d2ed18bf0f253001cca": "dogecoin-1.14.2-i686-pc-linux-gnu.tar.gz",
  "10c400c8f2039b1f804b8a533266201a9e4e3b32a8854501e8a43792e1ee78e6": "dogecoin-1.14.2-x86_64-linux-gnu.tar.gz",

  "65671f9854fe04815a4a849e6cdd5b1701fa04627cd2acc68cfd1de2561f70e5": "dogecoin-1.14.3-aarch64-linux-gnu.tar.gz",
  "e572d5af93f8ff4a5178e1edbbc151410f311097a17a619c43ca92de0ef4e51a": "dogecoin-1.14.3-arm-linux-gnueabihf.tar.gz",
  "c998e35ba3d8caf5bf5f2cec79c80e8cfea0ee9ccbaa5bff81b76ae72df9bbb1": "dogecoin-1.14.3-i686-pc-linux-gnu.tar.gz",
  "a95cc29ac3c19a450e9083cc3ac24b6f61763d3ed1563bfc3ea9afbf0a2804fd": "dogecoin-1.14.3-x86_64-linux-gnu.tar.gz",

  "72ee42424835cdfb4111b284c98f78919b7a9ede6f8d509b2abe31f7b3eb1f09": "dogecoin-1.14.4-aarch64-linux-gnu.tar.gz",
  "d023b7a6dfc5d92b1635f0fa03e14c9fc787a3eae94fba0cc3aca53b62a8e9ac": "dogecoin-1.14.4-arm-linux-gnueabihf.tar.gz",
  "6e93f5edccf528b44112f2088be3ac8f4f44151a757754da09c8c53cdd725815": "dogecoin-1.14.4-i686-pc-linux-gnu.tar.gz",
  "6266235abe4bcbd41ea57bdf42f11ef89aa69f0386e8c8846d5228af69e7fa13": "dogecoin-1.14.4-x86_64-linux-gnu.tar.gz",

  "f3bc387f393a0d55b6f653aef24febef6cb6f352fab2cbb0bae420bddcdacd1c": "dogecoin-1.14.5-aarch64-linux-gnu.tar.gz",
  "dfdcdc6bb36076e7634cc8ed89138ec0383d73ba42b3e7ecfa9279b8949bce6b": "dogecoin-1.14.5-arm-linux-gnueabihf.tar.gz",
  "7e7dd731ecfb2b78d6cc50d013ebf5faceeab50c59ffa2ab7551167b1bb81f08": "dogecoin-1.14.5-i686-pc-linux-gnu.tar.gz",
  "17a03f019168ec5283947ea6fbf1a073c1d185ea9edacc2b91f360e1c191428e": "dogecoin-1.14.5-x86_64-linux-gnu.tar.gz",

  "87419c29607b2612746fccebd694037e4be7600fc32198c4989f919be20952db": "dogecoin-1.14.6-aarch64-linux-gnu.tar.gz",
  "d0b7f5f4fbabb6a10078ac9cde1df7eb37bef4c2627cecfbf70746387c59f914": "dogecoin-1.14.6-arm-linux-gnueabihf.tar.gz",
  "3e60c4c818cb44abcca5b3bf9eff6baf86834c762e41d886c19bd721c00d0e24": "dogecoin-1.14.6-i686-pc-linux-gnu.tar.gz",
  "fe9c9cdab946155866a5bd5a5127d2971a9eed3e0b65fb553fe393ad1daaebb0": "dogecoin-1.14.6-x86_64-linux-gnu.tar.gz"

}

@contextlib.contextmanager
def pushd(new_dir) -> None:
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


def download_binary(tag, args) -> int:
    if Path(tag).is_dir():
        if not args.remove_dir:
            print('Using cached {}'.format(tag))
            return 0
        shutil.rmtree(tag)
    Path(tag).mkdir()
    bin_path = 'bin/dogecoin-core-{}'.format(tag[1:])
    match = re.compile('v(.*)(rc[0-9]+)$').search(tag)
    if match:
        bin_path = 'bin/dogecoin-core-{}/test.{}'.format(
            match.group(1), match.group(2))
    tarball = 'dogecoin-{tag}-{platform}.tar.gz'.format(
        tag=tag[1:], platform=args.platform)
    tarballUrl = f'{args.binary_url}/{tarball}'

    print('Fetching: {tarballUrl}'.format(tarballUrl=tarballUrl))

    header, status = subprocess.Popen(
        ['curl', '--head', tarballUrl], stdout=subprocess.PIPE).communicate()
    if re.search("404 Not Found", header.decode("utf-8")):
        print("Binary tag was not found")
        return 1

    curlCmds = [
        ['curl', '--remote-name', tarballUrl]
    ]

    for cmd in curlCmds:
        ret = subprocess.run(cmd).returncode
        if ret:
            return ret

    hasher = hashlib.sha256()
    with open(tarball, "rb") as afile:
        hasher.update(afile.read())
    tarballHash = hasher.hexdigest()

    if tarballHash not in SHA256_SUMS or SHA256_SUMS[tarballHash] != tarball:
        print("Checksum did not match")
        return 1
    print("Checksum matched")

    # Extract tarball
    ret = subprocess.run(['tar', '-zxf', tarball, '-C', tag,
                          '--strip-components=1',
                          'dogecoin-{tag}'.format(tag=tag[1:])]).returncode
    if ret:
        return ret

    Path(tarball).unlink()
    return 0


def build_release(tag, args) -> int:
    githubUrl = "https://github.com/dogecoin/dogecoin"
    if args.remove_dir:
        if Path(tag).is_dir():
            shutil.rmtree(tag)
    if not Path(tag).is_dir():
        # fetch new tags
        subprocess.run(
            ["git", "fetch", githubUrl, "--tags"])
        output = subprocess.check_output(['git', 'tag', '-l', tag])
        if not output:
            print('Tag {} not found'.format(tag))
            return 1
    ret = subprocess.run([
        'git', 'clone', githubUrl, tag
    ]).returncode
    if ret:
        return ret
    with pushd(tag):
        ret = subprocess.run(['git', 'checkout', tag]).returncode
        if ret:
            return ret
        host = args.host
        if args.depends:
            with pushd('depends'):
                ret = subprocess.run(['make', 'NO_QT=1']).returncode
                if ret:
                    return ret
                host = os.environ.get(
                    'HOST', subprocess.check_output(['./config.guess']))
        config_flags = '--prefix={pwd}/depends/{host} '.format(
            pwd=os.getcwd(),
            host=host) + args.config_flags
        cmds = [
            './autogen.sh',
            './configure {}'.format(config_flags),
            'make',
        ]
        for cmd in cmds:
            ret = subprocess.run(cmd.split()).returncode
            if ret:
                return ret
        # Move binaries, so they're in the same place as in the
        # release download
        Path('bin').mkdir(exist_ok=True)
        files = ['dogecoind', 'dogecoin-cli', 'dogecoin-tx']
        for f in files:
            Path('src/'+f).rename('bin/'+f)
    return 0


def check_host(args) -> int:
    args.host = os.environ.get('HOST', subprocess.check_output(
        './depends/config.guess').decode())
    if args.download_binary:
        platforms = {
            'x86_64-*-linux*': 'x86_64-linux-gnu',
            'x86_64-apple-darwin*': 'osx64',
        }
        args.platform = ''
        for pattern, target in platforms.items():
            if fnmatch(args.host, pattern):
                args.platform = target
        if not args.platform:
            print('Not sure which binary to download for {}'.format(args.host))
            return 1
    return 0


def main(args) -> int:
    Path(args.target_dir).mkdir(exist_ok=True, parents=True)
    print("Releases directory: {}".format(args.target_dir))
    ret = check_host(args)
    if ret:
        return ret
    if args.download_binary:
        with pushd(args.target_dir):
            for tag in args.tags:
                ret = download_binary(tag, args)
                if ret:
                    return ret
        return 0
    args.config_flags = os.environ.get('CONFIG_FLAGS', '')
    args.config_flags += ' --without-gui --disable-tests --disable-bench'
    with pushd(args.target_dir):
        for tag in args.tags:
            ret = build_release(tag, args)
            if ret:
                return ret
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', '--remove-dir', action='store_true',
                        help='remove existing directory.')
    parser.add_argument('-d', '--depends', action='store_true',
                        help='use depends.')
    parser.add_argument('-b', '--download-binary', action='store_true',
                        help='download release binary.')
    parser.add_argument('-t', '--target-dir', action='store',
                        help='target directory.', default='releases')
    parser.add_argument('-u', '--binary-url', action='store',
                        help='binary base url', default=DEFAULT_BINARY_URL)
    parser.add_argument('tags', nargs='+',
                        help="release tags. e.g.: v0.18.1 v0.20.0rc2")
    args = parser.parse_args()
    sys.exit(main(args))

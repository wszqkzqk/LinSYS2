project('linsys2',
        'c',
        license : 'GPL-2.0-or-later',
        meson_version : '>= 1.1.0',
        # prefix IS the toolchain's private home: every pacman install rule
        # then lands under it. system_prefix carries the system-facing entries.
        default_options : ['prefix=/usr/lib/linsys2-pacman'])

system_prefix = get_option('system_prefix')

# Patch the vendored pacman before meson reads it.
run_command(find_program('scripts/apply-patches.sh'), check : true)

# Reconfigure when a patch file changes so the script above re-runs.
patch_list = run_command(
  'sh', '-c', 'ls "@0@"/patches/*.patch'.format(meson.current_source_dir()),
  check : true).stdout().split()
foreach p : patch_list
  configure_file(input : p, output : p.split('/')[-1], copy : true)
endforeach

# Force the subproject prefix so its own project() defaults cannot win.
subproject('msys2-pacman', default_options : [
  'prefix=' + get_option('prefix'),
  'sysconfdir=etc',
  'localstatedir=var',
  'scriptlet-shell=/bin/bash',
  'pkg-ext=.pkg.tar.zst',
  'buildstatic=false',
  # arch-meson's --auto-features=enabled would require asciidoc
  'doc=disabled',
])

# r<count>.<date>.<hash>, matching the PKGBUILD pkgver()
version = 'unknown'
git = find_program('git', required : false)
if git.found() and run_command(git, 'rev-parse', '--is-inside-work-tree',
                               check : false).returncode() == 0
  count = run_command(git, 'rev-list', '--count', 'HEAD', check : true).stdout().strip()
  date = run_command(git, 'log', '-1', '--format=%cd', '--date=format:%Y%m%d',
                     check : true).stdout().strip()
  hash = run_command(git, 'rev-parse', '--short', 'HEAD', check : true).stdout().strip()
  version = 'r@0@.@1@.@2@'.format(count, date, hash)
endif

version_py = configure_file(
  input : 'python/linsys2/_version.py.in',
  output : '_version.py',
  configuration : {'version' : version})

paths_py = configure_file(
  input : 'python/linsys2/_paths.py.in',
  output : '_paths.py',
  configuration : {'private_prefix' : get_option('prefix'),
                   'bin_dir' : system_prefix / 'bin'})

# Python package -> <system_prefix>/lib/linsys2/linsys2
py_pkg_dir = system_prefix / 'lib' / 'linsys2' / 'linsys2'
install_data(
  ['python/linsys2/__init__.py',
   'python/linsys2/common.py',
   'python/linsys2/cli_linsys2.py',
   'python/linsys2/cli_pacman.py',
   'python/linsys2/cli_makepkg.py'],
  install_dir : py_pkg_dir)
install_data([version_py, paths_py], install_dir : py_pkg_dir)
install_data(['python/linsys2/shims/cygpath',
              'python/linsys2/shims/uname'],
             install_dir : py_pkg_dir / 'shims')

# Entry points -> <system_prefix>/bin. Absolute shebang, not env: an MSYS2
# environment's own Windows python3 can end up first on PATH.
py = import('python').find_installation('python3')
foreach entry : ['linsys2', 'linsys2-pacman', 'linsys2-makepkg']
  configure_file(
    input : 'scripts' / entry,
    output : entry,
    configuration : {'PYTHON3' : py.full_path()},
    install : true,
    install_dir : system_prefix / 'bin',
    install_mode : 'rwxr-xr-x')
endforeach

install_data('etc/makepkg_linsys2.conf',
             install_dir : get_option('prefix') / 'etc')
install_data(
  ['etc/makepkg_linsys2.d/ucrt64.conf',
   'etc/makepkg_linsys2.d/clang64.conf',
   'etc/makepkg_linsys2.d/clangarm64.conf'],
  install_dir : get_option('prefix') / 'etc' / 'makepkg_linsys2.d')

install_data(
  ['vendor/msys2-keyring/msys2.gpg',
   'vendor/msys2-keyring/msys2-trusted',
   'vendor/msys2-keyring/msys2-revoked'],
  install_dir : get_option('prefix') / 'share' / 'pacman' / 'keyrings')

install_data('README.md', install_dir : system_prefix / 'share' / 'doc' / 'linsys2-pacman')
install_data('COPYING', install_dir : system_prefix / 'share' / 'licenses' / 'linsys2-pacman')

# pacman's bash-completion is useless under the private prefix
meson.add_install_script(
  'sh', '-c',
  'rm -rf "$MESON_INSTALL_DESTDIR_PREFIX"/share/bash-completion')

test('unit', py,
     args : ['-m', 'unittest', 'discover', '-s',
             meson.current_source_dir() / 'tests'],
     env : ['PYTHONPATH=' + meson.current_source_dir() / 'python'],
     suite : 'linsys2',
     timeout : 60)

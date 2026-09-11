project('alltool-c', 'c',
  version: '2.0.0',
  default_options: ['warning_level=3', 'werror=false', 'c_std=c11'])

cc = meson.get_compiler('c')

openssl_dep = dependency('openssl')
cjson_dep = dependency('libcjson')
rt_dep = dependency('rt')
pthread_dep = dependency('threads')

shm_sources = ['alltool_shm.c']
compiler_sources = ['alltool_compiler.c']
sudo_sources = ['alltool_sudo.c']
runner_sources = ['alltool_runner.c']

alltool_shm_lib = shared_library('alltool_shm', shm_sources,
  dependencies: [rt_dep, pthread_dep],
  install: true,
  install_dir: '/home/debian/.config/alltool/bin')

alltool_compiler_lib = shared_library('alltool_compiler', compiler_sources,
  dependencies: [openssl_dep, cjson_dep],
  install: true,
  install_dir: '/home/debian/.config/alltool/bin')

alltool_sudo_lib = shared_library('alltool_sudo', sudo_sources,
  dependencies: [openssl_dep, cjson_dep],
  install: true,
  install_dir: '/home/debian/.config/alltool/bin')

alltool_runner = executable('alltool_runner', runner_sources,
  dependencies: [alltool_shm_lib, alltool_compiler_lib, alltool_sudo_lib, rt_dep, pthread_dep],
  install: true,
  install_dir: '/home/debian/.config/alltool/bin')

pkg = import('pkgconfig')
pkg.generate(
  name: 'alltool',
  description: 'AllTool C Components',
  version: '2.0.0',
  libraries: [alltool_shm_lib, alltool_compiler_lib, alltool_sudo_lib],
  requires: ['openssl', 'libcjson']
)
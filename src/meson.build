sources = files(
    'main.rs',
)

app_name = meson.project_name()

if get_option('offline')
  offline = '--offline'
else
  offline = ''  
endif

speech_provider_dep = dependency('speech-provider-1.0',
                                 version: '>= 1.0.1',
                                 required: false)
espeak_provider_depends = []
espeak_provider_env = environment()

if not speech_provider_dep.found()
  speech_provider_proj = subproject('libspeechprovider',
                                    default_options: ['tests=false',
                                                      'docs=false',
                                                      'introspection=false'])
  espeak_provider_depends = [ speech_provider_proj.get_variable('speech_provider_lib') ]
  espeak_provider_env.set('PKG_CONFIG_PATH',
                          meson.global_build_root() / 'meson-uninstalled')
endif

custom_target('speech-provider-espeak',
              build_by_default: true,
              input: [sources],
              output: app_name,
              depends: espeak_provider_depends,
              env: espeak_provider_env,
              console: true,
              install: true,
              install_dir: bindir,
              command: [cargo_script,
                  meson.project_build_root(),
                  meson.project_source_root(),
                  '@OUTPUT@',
                  app_name,
                  offline])

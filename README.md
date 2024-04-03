# An eSpeak-NG Speech Provider

This is a Spiel speech provider that features the very capable eSpeak-NG engine.

## Installation

TODO: Offer Flatpaks

## Build instructions

```sh
meson setup build
meson compile -C build
```

To run the provider without installing:
```sh
meson devenv -C build
./src/speech-provider-espeak
```
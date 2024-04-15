# An eSpeak-NG Speech Provider

This is a Spiel speech provider that features the very capable eSpeak-NG engine.

## Installation

Add the Flatpak repository:
```sh
flatpak remote-add --user espeak https://project-spiel.org/speech-provider-espeak/speech-provider-espeak.flatpakrepo
```

Install the eSpeak Provider:
```sh
flatpak install org.espeak.Speech.Provider
```

To voices available to install:
```sh
flatpak remote-ls espeak
```

Install an eSpeak voice:
```sh
flatpak install org.espeak.Speech.Provider.Voice.Alex
```

> [!IMPORTANT]
> Due to Flatpak limitations, you need to restart the speech provider after you install new voices.
> Do this with: `pkill -f speech-provider-espeak`

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
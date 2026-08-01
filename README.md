# <img src='gg.jpg' card_color='#00ff00' width='50' height='50' style='vertical-align:bottom'/> GGWave Skill

Voice interface for the [ovos-audio-transformer-plugin-ggwave](https://github.com/OpenVoiceOS/ovos-audio-transformer-plugin-ggwave) plugin.

This skill lets a user turn ggwave on and off by voice. When enabled, ggwave stays on for
15 minutes. After that time, the user must enable it again.

The skill recognizes several spoken names for ggwave:
- ggwave
- audio code
- audio qr code
- audio data

## Install

`ovos-skill-ggwave` is an OVOS skill. Install it with `pip`:

```bash
pip install ovos-skill-ggwave
```

## Usage

Ask the assistant to turn ggwave on or off. Example phrases:
- "start ggwave"
- "allow audio data"
- "disable audio codes"

## Related

- [ovos-audio-transformer-plugin-ggwave](https://github.com/OpenVoiceOS/ovos-audio-transformer-plugin-ggwave), the plugin this skill controls
- [ggwave](https://github.com/ggerganov/ggwave), the underlying audio-data-over-sound library
- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager), which provides the `opm.skill` entry point this skill registers with

## License

Apache-2.0

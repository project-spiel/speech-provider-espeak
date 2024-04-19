import pathlib
import json
import urllib.request
import urllib.parse

MANIFEST_TEMPLATE = '''{{
  "app-id": "org.espeak.Speech.Provider.Voice.{escaped_name}",
  "runtime": "org.espeak.Speech.Provider",
  "runtime-version": "master",
  "sdk": "org.freedesktop.Sdk//23.08",
  "build-extension": true,
  "modules": [
    {{
      "name": "espeak-ng",
      "buildsystem": "simple",
      "build-commands": [
        "install -D -m644 \\"espeak-ng-data/voices/\\!v/{name}\\" \\"${{FLATPAK_DEST}}/voices/{name}\\""
      ],
      "sources": [
        {{
          "type": "git",
          "url": "https://github.com/espeak-ng/espeak-ng.git",
          "tag": "1.51.1",
          "commit": "34762a2b9621d3643e67a00642984c21f0626bdc",
          "x-checker-data": {{
            "type": "git",
            "tag-pattern": "^([\\\\d.]+)$"
          }}
        }}
      ]
    }}
  ]
}}
'''

response = urllib.request.urlopen('https://api.github.com/repos/espeak-ng/espeak-ng/git/trees/1.51.1?recursive=1')
data = json.load(response)

p = pathlib.Path("_voices/")
p.mkdir(parents=True, exist_ok=True)

f = filter(lambda d: d["path"].startswith("espeak-ng-data/voices/!v/"), data["tree"])
for obj in f:
  name = pathlib.Path(obj["path"]).name
  escaped_name = urllib.parse.quote(name.replace(" ", "_"))
  manifest = f"_voices/org.espeak.Speech.Provider.Voice.{escaped_name}.json"
  mf = open(manifest, "w")
  mf.write(MANIFEST_TEMPLATE.format(name=name, escaped_name=escaped_name))
  mf.close()
  print(manifest)

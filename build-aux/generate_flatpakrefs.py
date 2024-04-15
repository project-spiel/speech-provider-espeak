import pathlib
import json
import urllib.request
import urllib.parse

FLATPAKREF_TEMPLATE = '''[Flatpak Ref]
Version=1
Title={title}
Description={desc}
Homepage=https://project-spiel.org
Name={fullname}
Url=https://project-spiel.org/speech-provider-espeak/repo
RuntimeRepo=https://flathub.org/repo/flathub.flatpakrepo
GPGKey=mDMEZZWaSxYJKwYBBAHaRw8BAQdACV6w6+Bbovz6Vpyx1rQ8ZCnfUnWSLUWb5EoLAmKPyFW0EGVlZWpheUBnaXRodWIuaW+ImQQTFgoAQRYhBBmmkocqhfIfyHWwkX7vHImPyEmfBQJllZpLAhsDBQkFo5qABQsJCAcCAiICBhUKCQgLAgQWAgMBAh4HAheAAAoJEH7vHImPyEmfPqAA/jY9uHOKRD9/ByFsly+d4r4PGRiEuygZpsdTCkE/P9mVAP4w10NaV/SM4YEKpNLNjlLxahq+1gw1HjjzRLHaUL8aCrg4BGWVmksSCisGAQQBl1UBBQEBB0DUvpNB4l+YNk45u1UnaWcgCl8NnHCbB+AG3gsTedcDegMBCAeIeAQYFgoAIBYhBBmmkocqhfIfyHWwkX7vHImPyEmfBQJllZpLAhsMAAoJEH7vHImPyEmf1PYBANgR1d/R6jqgQg7TuP3Ic3hTZHkMsVecWDhGI10tahiDAQCjGk2tex7nBvhiwEiagD5o+aqBfoR6Ezb4rKkarf8hBA==
'''

def write_flatpakref(fullname, title, desc):
  fpref = f"{fullname}.flatpakref"
  mf = open(fpref, "w")
  mf.write(FLATPAKREF_TEMPLATE.format(desc=desc, title=title, fullname=fullname))
  mf.close()
  print(fpref)

response = urllib.request.urlopen('https://api.github.com/repos/espeak-ng/espeak-ng/git/trees/1.51.1?recursive=1')
data = json.load(response)

write_flatpakref("org.espeak.Speech.Provider", "eSpeakNG Speech Provider", "A Spiel speech provider for the eSpeakNG engine")
f = filter(lambda d: d["path"].startswith("espeak-ng-data/voices/!v/"), data["tree"])
for obj in f:
  name = pathlib.Path(obj["path"]).name
  escaped_name = urllib.parse.quote(name.replace(" ", "_"))
  write_flatpakref(f"org.espeak.Speech.Provider.Voice.{escaped_name}", f"eSpeakNG {name}", f"{name} voice for eSpeakNG Provider")

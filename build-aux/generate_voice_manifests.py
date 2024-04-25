import pathlib
import json
import urllib.request
import urllib.parse
from collections import OrderedDict

METAINFO_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<component type="addon">
  <id>org.espeak.Speech.Provider.Voice.{escaped_name}</id>

  <name>{name}</name>
  <summary>The {name} voice for eSpeak</summary>

  <metadata_license>MIT</metadata_license>
  <project_license>LGPL-3.0-or-later</project_license>

  <extends>
    <id>org.espeak.Speech.Provider</id>
  </extends>

  <description>
    <p>
      The {name} voice for eSpeak
    </p>
  </description>

</component>
'''

MANIFEST_TEMPLATE = '''{
  "app-id": "",
  "runtime": "org.espeak.Speech.Provider",
  "runtime-version": "master",
  "sdk": "org.freedesktop.Sdk//23.08",
  "build-extension": true,
  "modules": [
    {
      "name": "espeak-ng",
      "buildsystem": "simple",
      "build-commands": [],
      "sources": [
        {
          "type": "git",
          "url": "https://github.com/espeak-ng/espeak-ng.git",
          "tag": "1.51.1",
          "commit": "34762a2b9621d3643e67a00642984c21f0626bdc",
          "x-checker-data": {
            "type": "git",
            "tag-pattern": "^([\\\\d.]+)$"
          }
        }
      ]
    }
  ]
}
'''

MBROLA_DATA_TEMPLATE = '''{
  "name": "mbrola-data",
  "buildsystem": "simple",
  "build-commands": [],
  "sources": [
    {
      "type": "file",
      "url": "",
      "sha256": ""
    }
  ]
}'''

MBROLA_FILES = [
  ['af1', '9760046e3f2b007f8c0279d321e5e934afaa8cfb7ec075241108a0e8f3730c7c'],
  ['ar1', '4bf5dc3769c1e9431e80dd59e5014dc524c34db0797769062e379fbc4faac4b1'],
  ['ar2', '8791680f98b78392b1dd282bf59a240144dd0262e77453461ee284f344a382c0'],
  ['br1', 'cba475ecb25ee0f6af657e6f35460f3e2f102f8c3eafb0e413c9a3501f6a112f'],
  ['br2', 'ec26d3d229e5384477c99be1f434eb71de5f18e46f6b9a5eb6092f7f0f09c2f6'],
  ['br3', '6c8c8210affc0866f5bce4a4422330fb840bf1507788543dc36c3f6722d6c9a8'],
  ['br4', 'c93fa66ebfab790bc255cb77499e7eca055ac1216df0f336fdcc2037c4271bbc'],
  ['bz1', 'dbe189bca19083e4b988811b504316e37c47142854d42694f681c7436f1811c1'],
  ['ca1', 'dd2d1ecb4e8a08a1bedfc9429e91aa50b9352772ad35de86acf495fbf03db69a'],
  ['ca2', '7ed9450b8ff8db4af3de15356f158b8e1c0cbe1fb7b4be4e4894147068b1089e'],
  ['cn1', 'f1b726d0739e9e3ab95831e5750fae5be5cfb143f2867faabe79dc873118fa33'],
  ['cr1', 'b5f85d7c4a8da013a4916945cb567d67d2731ca74a64c30513baa40f119cec44'],
  ['cz1', '1e2f577c35f7a13629087c92b58679c27a2e1b04bd7700805c6094e814ee182e'],
  ['cz2', '23f78d232781ce0785fbe1a7549efabc44b92fe7a64f8f2bff0d9aa743455d1f'],
  ['de1', '405417e16fa10bb777514b8b5c883d6e3427d6d9cdbb92c61a1cc4aba4d65e88'],
  ['de2', '5fb968f9b5a8fe594958d4a8b77c388c38c39f9a855d08aba4d500c62f899be1'],
  ['de3', '480ed66b78b22aebdfe9cc82af078edbd53525efe793bfc22ef6d1047fa48f61'],
  ['de4', '78c988d6df3948df369aa5c0d13a2e3668b7a42d0f5e4f0e21d31523f61e502a'],
  ['de5', '9df792dc04dbf199c041ec60a1e2264c222bb53e40c577cbdbadd4b4b64eeda0'],
  ['de6', '7c2e7d36b19e9461f28efe531fcd0aade1c4e704b5e2718416b23d9800ef5a88'],
  ['de7', '90d4379057f7e313209a57b3182083ea525bf96aeba491349c4443ac8b5327a1'],
  ['de8', '77f826f8ff4fb5289b80617f160c5943b7096262b1e80988b8794864fb6e0e95'],
  ['ee1', '94e6aefe1706ed6303d13514ae7fac9669eda121e0d060d76429fe7c43f95258'],
  ['en1', 'edb8eaae6f0e38493d88ed627518632e6ff8a3843bcf08474a1a70aa786fd99f'],
  ['es1', 'fba1c76b70cd26b46c190780d6af49f1d4d2d945642869c3702d609bca7dfb7c'],
  ['es2', '6ec601537dc99949861c3e3d6d5f329bd0b87cbef61d988bd726c985b1144ac5'],
  ['es3', 'c098cb7e7c5f43b508d73811dc980db261df02cf53720a12a8eb761775b71790'],
  ['es4', '26b6f8e9c717f8cfb5c067fcb3c25ccf1d05d4edf894b0090b87a16c4f3656fd'],
  ['fr1', 'b2e9693ab8712c027adf30393aec58291c162be97f5164a209a6a5a7835a53da'],
  ['fr2', 'e6269d53b264f5743091397a37a75587e1f16c6c890fa55b2b5f88c67c100339'],
  ['fr3', '49450f30f01f87e9c17d1364ba2d46fad8a692b7fe6b59347d32dd423bc1c275'],
  ['fr4', '0c0a916fc32382a8b1f252fdc5c269a2c8dcb8b440971b9bd1960c02b7cb0c93'],
  ['fr5', 'f840031f8267c5eb21f40a94099f170ad6a0871949568bbabbe3287415de79dd'],
  ['fr6', '9fc122671e752d5e18c5c73f49b6beece999f2836e42aa0d0862777edcd643a2'],
  ['fr7', 'b914fc5204955cad52d91bc816db61a1f8a44eba5224e4e581ec201e45c41327'],
  ['gr1', 'b9f2d8b16b12629f981aed3d2f6ba885ab6752da6521ad40522d2c0086f5fee9'],
  ['gr2', 'd010de77c61d548582349a17f353a1c9f05015b60a028479601c46d9dbfc02a9'],
  ['hb1', '1093d4da40399b8999032bd44c37ef6cfb99ef2b5317771a2c497d8bd5b84749'],
  ['hb2', '57b157d6baca885e234c0e58e3ffa4341d35a58406bb8ba03c706b3cfb591886'],
  ['hn1', 'dbb2f84a77f0bd6e652e5cfcd8926da8051fd4393f6384fd554ae4d0d2f09504'],
  ['hu1', 'fd18e03518c0cd58de82422c5a6661f1c2f894c396048167293591ed36444d0a'],
  ['ic1', '1764451ebe76f5d4f5efa67937bffe63b8b3da142ccda24cc7b7718999da9c13'],
  ['id1', 'ef0254a32f632468b799c95ff9256bd6f81aa8900f619262618959ad68fa75d0'],
  ['in1', 'e7a5178af7fac0953c1570dd2d93f85d5ae67cfc272177ed1ca45a7be9d692d4'],
  ['in2', '7ea599a540c6ae64483f9ef86405e8031d7bcd9d85884d00e17815a17ed0368f'],
  ['ir1', 'acbae88122e1107c9b1ecd54ba8b926eda8f8a1170f8595b69f3828b7db35b97'],
  ['it1', 'f543f9d79c5eac3046d08c85c24381982d1601bd6ec87cb5898e51097db6bbe1'],
  ['it2', '48eeeb13c93f2a1487a710d232cd11e65187e4a74c3cb9f6d5cb1085ef50bfdd'],
  ['it3', '0ce45edcfe858eeea5294f8a00a29b5f934100e5bea92f2fb3d11dccb72e00c9'],
  ['it4', '807a3aba68209b154ce8d3d953165d06092023beee1186ec622c938a33f7692a'],
  ['jp1', 'ee84315b2c71692e2537e45392dc54af87448212b4d1f20089b32660b9530b5d'],
  ['jp2', 'c6ee2980507c2e7b6bf6c9b5f401e4bde5b4e30a611f82360934279089278df1'],
  ['jp3', 'd4220ffef85d86ecf8e1c1a9f1a2a3ee57ee85ea5e88b2680e7d0668d82245e6'],
  ['la1', '14f0760405123f5ce40c7cf240960f6822fc12c092d9cb6d2b7179f23e3ed3b6'],
  ['lt1', 'caecd03a27c9fd064dfc718ba28e3523fd6eb5625197eb11902ccbb8671352d7'],
  ['lt2', '855b49a11f962e3e61223f96187f7cbb60844c52748d3ebab17cb0a0ea2b0062'],
  ['ma1', 'bdd754fcc98ebd236d7aae16a5d59f2a7fe0c4219896fdf613c8375bb5d74865'],
  ['mx1', '4b4e09c5eea3c2f385ce51eb280c17223118b560b96c0339deb74dee0d7224dc'],
  ['mx2', '75a5b11e0c8274698856d62ecfc21768fd5e40fb06d0705059c0e691fbc93f9c'],
  ['nl1', 'f31c29fcb59101aad91c12aaf8c02e88d1ef1f712e64c387193fff4686a6e2d9'],
  ['nl2', 'f307f28b504d22f151131eb2299f40bb9872586a77d58d7828514da465d68155'],
  ['nl3', '7cb2769500efc33563d82c7ee8162bc7cf174d3b75c750e2f4f3740bc9e26ba2'],
  ['nz1', '7e23559bc7252971097b2dfd139ff0a4f649c521f15a16c92b89d2e1679f9eac'],
  ['pl1', '994e5e4719b9f788c88e7aea4d8a13dd0674c6ff6b118c68450c1374ccc83d5c'],
  ['pt1', '89e368a68a7a3bcff4eb2d934d26d8159c34fc7ccbf5750ac9ca31297054d24e'],
  ['ro1', '5a0e8d89c3d0e163d620385b291a223eb831abaa7b6856fcf1b57096c4e57eb7'],
  ['sw1', '0bcb8c5b5af25cf6d5da97dbadcc7658f009652ab207793f9fda2b0d22c61fd7'],
  ['sw2', 'bf2f0de5d075c3bb8930128670d7a367a29dbae541fe053a8dbdc5dedba8105d'],
  ['tl1', '0b3598cdab4aee31dd2f035e96b19374e8afee0a3a80fcb9b05ef94e3f99e1eb'],
  ['tr1', 'f3860aadf656a663e0fadea836632e57309a47e17a9297f530a7a7ef48647372'],
  ['tr2', '9d6a9bac0c3ccb1800a914832d1c5d2766fdf1bb053c092c1657f321de32dca1'],
  ['us1', '9f1cd90de6334f43cb4f7348cacd0806fb414b0fbc762492bde7000b9e192a9a'],
  ['us2', '75f7f6b605945f4b65713c3ad1fba5be38fb720cde01bdc3d2facf988634c0d5'],
  ['us3', '7cc5c49e098f80091e34ed0bd50f0af3908ac2427fbbe7d2b16c57defb7611ec'],
  ['vz1', '63e0a5fa2c32f682e89e27a48633e536e5ebd211c9680021c95839e3c752612a']
]

def create_manifest(name, mbrola_data_checksum=None):
  escaped_name = urllib.parse.quote(name.replace(" ", "_"))
  if mbrola_data_checksum:
    escaped_name = f"mbrola_{escaped_name}"
  metainfo = METAINFO_TEMPLATE.format(name=name, escaped_name=escaped_name)

  manifest = json.loads(MANIFEST_TEMPLATE, object_pairs_hook=OrderedDict)
  manifest["app-id"] = f"org.espeak.Speech.Provider.Voice.{escaped_name}"
  espeak_module = manifest["modules"][0]
  espeak_module["build-commands"] = [
    f"install -Dm644 org.espeak.Speech.Provider.Voice.{escaped_name}.metainfo.xml -t ${{FLATPAK_DEST}}/share/metainfo/"
  ]

  if mbrola_data_checksum:
    espeak_module["build-commands"].append(f"install -D -m644 \"espeak-ng-data/voices/mb/mb-{name}\" \"${{FLATPAK_DEST}}/mb/{name}\"")
  else:
    espeak_module["build-commands"].append(f"install -D -m644 \"espeak-ng-data/voices/\\!v/{name}\" \"${{FLATPAK_DEST}}/voices/{name}\"")

  espeak_module["sources"].append(
        {
          "type": "inline",
          "contents": metainfo,
          "dest-filename": f"org.espeak.Speech.Provider.Voice.{escaped_name}.metainfo.xml"
        }
  )

  if mbrola_data_checksum:
    mbrola_module = json.loads(MBROLA_DATA_TEMPLATE, object_pairs_hook=OrderedDict)
    mbrola_module["build-commands"].append(f"install -D -m644 \"{name}\" \"${{FLATPAK_DEST}}/mbrola_data/{name}\"")
    mbrola_module["sources"][0]["url"] = f"https://github.com/numediart/MBROLA-voices/raw/master/data/{name}/{name}"
    mbrola_module["sources"][0]["sha256"] = mbrola_data_checksum
    manifest["modules"].append(mbrola_module)

  fname = f"_voices/org.espeak.Speech.Provider.Voice.{escaped_name}.json"
  mf = open(fname, "w")
  mf.write(json.dumps(manifest, indent=2).replace("\\!", "!"))
  mf.close()
  print(fname)

response = urllib.request.urlopen('https://api.github.com/repos/espeak-ng/espeak-ng/git/trees/1.51.1?recursive=1')
data = json.load(response)

p = pathlib.Path("_voices/")
p.mkdir(parents=True, exist_ok=True)

f = filter(lambda d: d["path"].startswith("espeak-ng-data/voices/!v/"), data["tree"])
for obj in f:
  name = pathlib.Path(obj["path"]).name
  create_manifest(name)

f = filter(lambda d: d["path"].startswith("espeak-ng-data/voices/mb/"), data["tree"])
available_mb_voices = [pathlib.Path(mb["path"]).name for mb in f]
for (name, checksum) in MBROLA_FILES:
  if f"mb-{name}" not in available_mb_voices:
    continue
  create_manifest(name, checksum)

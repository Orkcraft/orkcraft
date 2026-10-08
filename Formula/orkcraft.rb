# Written by tools/brew_formula.py for one commit: run it again rather than editing this file.
class Orkcraft < Formula
  include Language::Python::Virtualenv

  desc "Run many coding agents in one project, as a real-time strategy game"
  homepage "https://github.com/Orkcraft/orkcraft"
  url "https://github.com/Orkcraft/orkcraft/archive/233cd173c3a620c63bf3b6d67b4f2090b04e0ced.tar.gz"
  version "0.2.3"
  sha256 "44450e1c6f62305170fc8ca137e2ba5c2dd2425fb87ec8a2097f11c52318d31e"
  license "Apache-2.0"
  head "https://github.com/Orkcraft/orkcraft.git", branch: "main"

  depends_on "python@3.13"

  resource "attrs" do
    url "https://files.pythonhosted.org/packages/64/b4/17d4b0b2a2dc85a6df63d1157e028ed19f90d4cd97c36717afef2bc2f395/attrs-26.1.0-py3-none-any.whl"
    sha256 "c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309"
  end

  resource "bottle" do
    url "https://files.pythonhosted.org/packages/83/f6/b55ec74cfe68c6584163faa311503c20b0da4c09883a41e8e00d6726c954/bottle-0.13.4-py2.py3-none-any.whl"
    sha256 "045684fbd2764eac9cdeb824861d1551d113e8b683d8d26e296898d3dd99a12e"
  end

  resource "jsonschema" do
    url "https://files.pythonhosted.org/packages/69/90/f63fb5873511e014207a475e2bb4e8b2e570d655b00ac19a9a0ca0a385ee/jsonschema-4.26.0-py3-none-any.whl"
    sha256 "d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce"
  end

  resource "jsonschema-specifications" do
    url "https://files.pythonhosted.org/packages/41/45/1a4ed80516f02155c51f51e8cedb3c1902296743db0bbc66608a0db2814f/jsonschema_specifications-2025.9.1-py3-none-any.whl"
    sha256 "98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/b3/81/4da04ced5a082363ecfa159c010d200ecbd959ae410c10c0264a38cac0f5/markdown_it_py-4.2.0-py3-none-any.whl"
    sha256 "9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a"
  end

  resource "mdit-py-plugins" do
    url "https://files.pythonhosted.org/packages/a5/69/6da5581c6a7fede7dc261bf4e67d6adca4196f176b43288b55b3db395b6e/mdit_py_plugins-0.6.1-py3-none-any.whl"
    sha256 "214c82fb2ac524472ab6a5bcab1de80f73b50443e187f401bfd77efbc7c6481d"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/b3/38/89ba8ad64ae25be8de66a6d463314cf1eb366222074cfda9ee839c56a4b4/mdurl-0.1.2-py3-none-any.whl"
    sha256 "84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8"
  end

  resource "platformdirs" do
    url "https://files.pythonhosted.org/packages/c5/9b/6ce1ead737fe496611bda600c263b9a11ae7bd8f41bb13f9bd7e0a2c37a4/platformdirs-4.12.3-py3-none-any.whl"
    sha256 "080f3b39423b5abfca9a23d84c4e9795f54d395cd8459867a8ded44084fcd5f8"
  end

  resource "proxy-tools" do
    url "https://files.pythonhosted.org/packages/f2/cf/77d3e19b7fabd03895caca7857ef51e4c409e0ca6b37ee6e9f7daa50b642/proxy_tools-0.1.0.tar.gz"
    sha256 "ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010"
  end

  resource "pycparser" do
    url "https://files.pythonhosted.org/packages/0c/c3/44f3fbbfa403ea2a7c779186dc20772604442dde72947e7d01069cbe98e3/pycparser-3.0-py3-none-any.whl"
    sha256 "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/71/46/17f022dd3e953bf20a04a028a21ec746d942f8d2af30fa0f124fa0e6a684/pygments-2.21.0-py3-none-any.whl"
    sha256 "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9"
  end

  resource "pyte" do
    url "https://files.pythonhosted.org/packages/59/d0/bb522283b90853afbf506cd5b71c650cf708829914efd0003d615cf426cd/pyte-0.8.2-py3-none-any.whl"
    sha256 "85db42a35798a5aafa96ac4d8da78b090b2c933248819157fc0e6f78876a0135"
  end

  resource "pywebview" do
    url "https://files.pythonhosted.org/packages/3d/25/9491695c22c4842c5b3903b4dc172e0eecf67a27c0af34a71512c9b76a0a/pywebview-6.2.1-py3-none-any.whl"
    sha256 "9d07275f53894ab4d5e2e0e996227193e7187dec276d9b624dccbce029216b46"
  end

  resource "referencing" do
    url "https://files.pythonhosted.org/packages/2c/58/ca301544e1fa93ed4f80d724bf5b194f6e4b945841c5bfd555878eea9fcb/referencing-0.37.0-py3-none-any.whl"
    sha256 "381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/82/3b/64d4899d73f91ba49a8c18a8ff3f0ea8f1c1d75481760df8c68ef5235bf5/rich-15.0.0-py3-none-any.whl"
    sha256 "33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb"
  end

  resource "segno" do
    url "https://files.pythonhosted.org/packages/d6/02/12c73fd423eb9577b97fc1924966b929eff7074ae6b2e15dd3d30cb9e4ae/segno-1.6.6-py3-none-any.whl"
    sha256 "28c7d081ed0cf935e0411293a465efd4d500704072cdb039778a2ab8736190c7"
  end

  resource "textual" do
    url "https://files.pythonhosted.org/packages/fb/be/35261223d9416a0751cdff1c7b4a6f881387218a12d439fe22fefebc8c04/textual-8.2.8-py3-none-any.whl"
    sha256 "267375fd402dc8d981457212efa71f0e3365fd17bba144ba9bb3ed7563cb374a"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl"
    sha256 "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8"
  end

  on_macos do
    on_arm do
      resource "cffi" do
        url "https://files.pythonhosted.org/packages/55/41/4c7042f317b9217502988f0873af87e16ad606dc20f84e546e3e6ce9764c/cffi-2.1.1-cp313-cp313-macosx_11_0_arm64.whl"
        sha256 "19ee6127ee34de7d83ce3d371ebc5ed91addbdcc39f9ab15ce4eb35a4e534971"
      end

      resource "cryptography" do
        url "https://files.pythonhosted.org/packages/e5/56/d194340cc4a57535e82e1bee9e89667ac4b7c13b5d3f59686deae3094dd5/cryptography-50.0.2-cp311-abi3-macosx_11_0_arm64.whl"
        sha256 "fa8f5efb344d6908a1ce62f4a24e2e5780f825d6f53f5f50ec5ffacac72936cb"
      end

      resource "pyobjc-core" do
        url "https://files.pythonhosted.org/packages/1b/ed/a8bf040caf3704023d74086b7fb96cf4ed2e844e24bd94e5248ba214b700/pyobjc_core-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "950bd2d9c74634398c4e3d24ef2f213d4e23d705083697464fa67afedc53c1ad"
      end

      resource "pyobjc-framework-cocoa" do
        url "https://files.pythonhosted.org/packages/db/e1/5d9b04ebb60042b9cb49adc2d33115e2f2c2e4ff7d548017bfaff8b7f536/pyobjc_framework_cocoa-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "600b1723184ca094931330e79355274949965460e23de38628d601b5a967baf9"
      end

      resource "pyobjc-framework-quartz" do
        url "https://files.pythonhosted.org/packages/bb/ae/b515852dbe491171f2f2e2eb7739588a5eb7f36720a739545337b8c0d706/pyobjc_framework_quartz-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "0ec9751904ef975bf0789d760dc4fadcb400edc4ffe4a736eb54971968babe5c"
      end

      resource "pyobjc-framework-security" do
        url "https://files.pythonhosted.org/packages/f1/7f/cef885aaf57f7b8c1a5c141dc118094d07558f6c289fabd63690abf30059/pyobjc_framework_security-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "ca580d5f56e1222d63f1322a4fbf63be0bad77e77cca084290310df007b3fdde"
      end

      resource "pyobjc-framework-uniformtypeidentifiers" do
        url "https://files.pythonhosted.org/packages/79/c3/45ec69ed9fdcde5d0f229a031b610127c592d2c4674c3ff0e184d7f2741b/pyobjc_framework_uniformtypeidentifiers-12.2.2-py2.py3-none-any.whl"
        sha256 "1dc6a538df07c410e4bfd6457adcb0b663a5e0df331905dbe135bcfd3f89ae57"
      end

      resource "pyobjc-framework-webkit" do
        url "https://files.pythonhosted.org/packages/69/84/036541aaf4795c0022b6b1dda9a4e099e14b137012065a799a0b174947e5/pyobjc_framework_webkit-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "206f88451e1c3e152c72c16c2af2664646cd752a3007c9cda8029a9e3f0ec9a4"
      end

      resource "rpds-py" do
        url "https://files.pythonhosted.org/packages/57/71/a097d6552f837500fc36e6b23d09cfb9890c3cc47531f9ca64e149799615/rpds_py-2026.9.1-cp313-cp313-macosx_11_0_arm64.whl"
        sha256 "eba5d173f7d5708b22a93815017a4611873ed54db9f268077c0dd1ed99cfc858"
      end

      resource "wcwidth" do
        url "https://files.pythonhosted.org/packages/a0/07/cb6940e81134b7ed25fa312ee9ab536a63db0793b149f88a90e603ceace9/wcwidth-0.9.2-cp310-abi3-macosx_11_0_arm64.whl"
        sha256 "ae0800c5339423cc53d33a266ad264b42ba8aaa16d4464f6e6b1bee607f50b17"
      end

      resource "websockets" do
        url "https://files.pythonhosted.org/packages/ca/1e/621bb93f35ab7d337be98f1958294437527e2a1797089b5e734ddc5eec5f/websockets-17.2-cp313-cp313-macosx_11_0_arm64.whl"
        sha256 "cf8811d285acc91216368df7fb55cc8c9bf6fcd90eea42429c7186c7385a12b9"
      end
    end
    on_intel do
      depends_on "pkgconf" => :build
      depends_on "rust" => :build
      depends_on "openssl@3"

      resource "cffi" do
        url "https://files.pythonhosted.org/packages/a7/46/2e5fdde8555706dd98139a910ca11be02809f3f605ce956f655d0214e100/cffi-2.1.1-cp313-cp313-macosx_10_15_x86_64.whl"
        sha256 "9d2055050ea716bd38b7f7f1579c275386646b4894c155a3e2f3cd62ed41b7c6"
      end

      resource "cryptography" do
        url "https://files.pythonhosted.org/packages/9d/af/182eb91b0df3fe75c4d9f26fe70684569566745f6ba7e5c9c73a862c5252/cryptography-50.0.2.tar.gz"
        sha256 "7b46165bb56eb4704e2eaaf86f3c940d19154535d9b0ca7d6d590b04060e00d5"
      end

      resource "pyobjc-core" do
        url "https://files.pythonhosted.org/packages/1b/ed/a8bf040caf3704023d74086b7fb96cf4ed2e844e24bd94e5248ba214b700/pyobjc_core-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "950bd2d9c74634398c4e3d24ef2f213d4e23d705083697464fa67afedc53c1ad"
      end

      resource "pyobjc-framework-cocoa" do
        url "https://files.pythonhosted.org/packages/db/e1/5d9b04ebb60042b9cb49adc2d33115e2f2c2e4ff7d548017bfaff8b7f536/pyobjc_framework_cocoa-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "600b1723184ca094931330e79355274949965460e23de38628d601b5a967baf9"
      end

      resource "pyobjc-framework-quartz" do
        url "https://files.pythonhosted.org/packages/bb/ae/b515852dbe491171f2f2e2eb7739588a5eb7f36720a739545337b8c0d706/pyobjc_framework_quartz-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "0ec9751904ef975bf0789d760dc4fadcb400edc4ffe4a736eb54971968babe5c"
      end

      resource "pyobjc-framework-security" do
        url "https://files.pythonhosted.org/packages/f1/7f/cef885aaf57f7b8c1a5c141dc118094d07558f6c289fabd63690abf30059/pyobjc_framework_security-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "ca580d5f56e1222d63f1322a4fbf63be0bad77e77cca084290310df007b3fdde"
      end

      resource "pyobjc-framework-uniformtypeidentifiers" do
        url "https://files.pythonhosted.org/packages/79/c3/45ec69ed9fdcde5d0f229a031b610127c592d2c4674c3ff0e184d7f2741b/pyobjc_framework_uniformtypeidentifiers-12.2.2-py2.py3-none-any.whl"
        sha256 "1dc6a538df07c410e4bfd6457adcb0b663a5e0df331905dbe135bcfd3f89ae57"
      end

      resource "pyobjc-framework-webkit" do
        url "https://files.pythonhosted.org/packages/69/84/036541aaf4795c0022b6b1dda9a4e099e14b137012065a799a0b174947e5/pyobjc_framework_webkit-12.2.2-cp313-cp313-macosx_10_13_universal2.whl"
        sha256 "206f88451e1c3e152c72c16c2af2664646cd752a3007c9cda8029a9e3f0ec9a4"
      end

      resource "rpds-py" do
        url "https://files.pythonhosted.org/packages/83/ea/ee88fd9e756ff93fb6b1182a47ec09504a242620e33ce1d20679efefe841/rpds_py-2026.9.1-cp313-cp313-macosx_10_12_x86_64.whl"
        sha256 "a36b70596407634ca82d4b989a3729074a008537a0522e4c8046a67c729103e9"
      end

      resource "wcwidth" do
        url "https://files.pythonhosted.org/packages/59/1e/4532a81fb9dfbf4114a816775e0a36c3a64ee1d1f4bba2094e2da50be5dc/wcwidth-0.9.2-cp310-abi3-macosx_10_9_x86_64.whl"
        sha256 "7ef5a940bd5e30bac6e721f1a48fce0cd7bb3ece19e9c5d139e72c76c35cfd07"
      end

      resource "websockets" do
        url "https://files.pythonhosted.org/packages/cd/95/cb8881851abe2662730e6c61cc521b4c96513fdf9103a44f169afce2eba8/websockets-17.2-cp313-cp313-macosx_10_13_x86_64.whl"
        sha256 "8a829db795e3f87053904493d184b185c8eb1f497c852f434168ec856aa6f997"
      end
    end
  end

  on_linux do
    on_arm do
      resource "cffi" do
        url "https://files.pythonhosted.org/packages/37/6f/3b5ce4c3b2192d250f04908f2bfd91ef34552ec8f7716a5d4abdb8d67bb2/cffi-2.1.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl"
        sha256 "f16c709686a78c727bbbf059f92b0bf41c6fc60deec706d2dc19f529175a6125"
      end

      resource "cryptography" do
        url "https://files.pythonhosted.org/packages/38/6b/61a3f8d8c5e1e49a6cddccafc4015cc1c0021360ab0acb4080e7a423644a/cryptography-50.0.2-cp311-abi3-manylinux_2_28_aarch64.whl"
        sha256 "f9f6143a8c75945eb960d9eb98905a441394abfa24afaae239d514ffb2586480"
      end

      resource "rpds-py" do
        url "https://files.pythonhosted.org/packages/bd/b7/497e85768bf4e0d8ddbaa096a4cac31d1509251dee2728a8490aa367e0b5/rpds_py-2026.9.1-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
        sha256 "457866b85daf5034296666168b84a69e0b2e89dc4f1af102b46f6448a60b9063"
      end

      resource "wcwidth" do
        url "https://files.pythonhosted.org/packages/bc/f0/b8ef7758003d66b60f093695831a86dcc726aac01ee6446ffcbda27b61e3/wcwidth-0.9.2-cp310-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl"
        sha256 "674b518af28d38ee645ff97b74f5760abee5fad4bac74413bfc4b881ef2ce724"
      end

      resource "websockets" do
        url "https://files.pythonhosted.org/packages/f8/fe/0f0eda80bb441f54becdaf793eb20ee080926f8d2356388377cf262187e5/websockets-17.2-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl"
        sha256 "1110fbfd530c447380e6e6db88b7e43ffe33d54178f5b0ff0aaa5a280301e668"
      end
    end
    on_intel do
      resource "cffi" do
        url "https://files.pythonhosted.org/packages/95/95/86342356ff5953b3fb06f7ef7c5bee212d45e770abc7218d451b9148313c/cffi-2.1.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
        sha256 "a931079504ecc49efed7744c476a5c343a92fabf66dec2db95edb1b2fdc770e2"
      end

      resource "cryptography" do
        url "https://files.pythonhosted.org/packages/1a/f1/b474e930c4d910328780e3940da76f5aa5cbc48ce1fc14e44d239d9ea9db/cryptography-50.0.2-cp311-abi3-manylinux_2_28_x86_64.whl"
        sha256 "4061c0079120205fb760c58acab6443e217307dcf05e3702cf970e0689972856"
      end

      resource "rpds-py" do
        url "https://files.pythonhosted.org/packages/a0/36/76fab39973ee11e7f9f357c55138197bb01c86f6502cb76487e3b4f42db0/rpds_py-2026.9.1-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        sha256 "7868b85224291c6cb6759f9b5adb9745f486d226f62b16a614dd5a2a5ab2b35b"
      end

      resource "wcwidth" do
        url "https://files.pythonhosted.org/packages/db/6c/f940133c71427c208575910e981942bd78c98b1f7cd0d1425ca4b7457c04/wcwidth-0.9.2-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
        sha256 "751bef0ab404b6a1dc028b56b4b85d46486be1c55833f80da533e42dc691f389"
      end

      resource "websockets" do
        url "https://files.pythonhosted.org/packages/04/13/95a45eb410019772002d8f53d81396dad4120f7df39ca9962f86f5d7cd01/websockets-17.2-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl"
        sha256 "d87091c4347daadbcc0833b65812ff38d7350c67339625d4e4a512cf38e3e8ef"
      end
    end
  end

  def install
    # The `gui` extra: the wheels above are what it needs, installed as they are (brew's own
    # pip_install builds every package from source); pip builds an sdist among them, and the package.
    venv = virtualenv_create(libexec, "python3.13")
    wheels = resources.map do |r|
      r.fetch
      wheel = buildpath/"wheels"/File.basename(r.url)
      wheel.dirname.mkpath
      cp r.cached_download, wheel
      wheel
    end
    system "python3.13", "-m", "pip", "--python=#{libexec}/bin/python", "install",
           "--no-deps", "--no-compile", *wheels
    venv.pip_install_and_link buildpath
  end

  test do
    assert_match "orkcraft", shell_output("#{bin}/orkcraft --help")
    assert_equal version.to_s,
                 shell_output("#{libexec}/bin/python -c 'import orkcraft; print(orkcraft.__version__)'").strip
    system libexec/"bin/python", "-c", "import webview, websockets, cryptography, segno"
  end
end

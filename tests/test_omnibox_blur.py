"""Execute the patched frame's content-layer setup against a recording boundary.

This is a small construction-contract regression, not a rendered blur test.
Full Chromium compilation and a native Wayland visual check remain required.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_compatibility as compatibility

FRAME = "chrome/browser/ui/views/omnibox/rounded_omnibox_results_frame.cc"


class OmniboxBlurTests(unittest.TestCase):
    def test_only_classic_webui_results_get_linux_glass_backdrop(self):
        # Missing the content-layer filter caused transparent but sharp page
        # contents on Chromium 156. Exercise the actual constructor statements,
        # not a text match. The boundary records filter configuration only.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compatibility.fetch(FRAME, "156.0.8078.73", root)
            text = (ROOT / "chromium-glass-wayland.patch").read_text()
            marker = "--- a/" + FRAME + "\n"
            if marker in text:
                section = marker + text.split(marker, 1)[1].split("\n--- a/", 1)[0]
                applied = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1"],
                    cwd=root, input=section, text=True, capture_output=True)
                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            source = (root / FRAME).read_text()
            setup = source.split("contents_host->AddChildViewRaw(contents_.get());", 1)[1]
            setup = setup.split("\n  if (!draw_shadow_in_webui_) {", 1)[0]
            harness = r"""
#include <cassert>
#include <memory>
#include <initializer_list>
#define BUILDFLAG(x) (x)
#ifndef IS_LINUX
#define IS_LINUX 1
#endif
namespace features {
bool enabled;
bool IsGlassFrameEnabled() { return enabled; }
}
namespace gfx {
struct RoundedCornersF {
  float ul, ur, lr, ll;
  RoundedCornersF(float a, float b, float c, float d)
      : ul(a), ur(b), lr(c), ll(d) {}
};
}
struct Layer {
  bool opaque = true, fast = false;
  float blur = 0, quality = 1;
  gfx::RoundedCornersF corners{0,0,0,0};
  void SetFillsBoundsOpaquely(bool b) { opaque = b; }
  void SetBackgroundBlur(float b) { blur = b; }
  void SetBackdropFilterQuality(float q) { quality = q; }
  void SetRoundedCornerRadius(gfx::RoundedCornersF c) { corners = c; }
  void SetIsFastRoundedCorner(bool b) { fast = b; }
};
struct View {
  bool painted = false;
  Layer value;
  void SetPaintToLayer() { painted = true; }
  Layer* layer() { return &value; }
};
void run(bool enabled, bool webui, bool shadow) {
  features::enabled = enabled;
  int dummy = 0;
  auto* webui_content = webui ? &dummy : nullptr;
  const bool draw_shadow_in_webui_ = shadow;
  const int corner_radius = 12;
  auto contents_ = std::make_unique<View>();
""" + setup + r"""
  const bool expected = IS_LINUX && enabled && webui && !shadow;
  assert(contents_->painted == expected);
  assert(contents_->value.blur == (expected ? 18.0f : 0.0f));
  assert(contents_->value.opaque == !expected);
  if (expected) {
    assert(contents_->value.quality == 0.5f);
    assert(contents_->value.corners.ul == 0);
    assert(contents_->value.corners.ur == 0);
    assert(contents_->value.corners.lr == 12);
    assert(contents_->value.corners.ll == 12);
  }
}
int main() {
  for (bool glass : {false, true})
    for (bool webui : {false, true})
      for (bool shadow : {false, true})
        run(glass, webui, shadow);
}
"""
            cpp = root / "frame_setup.cc"
            cpp.write_text(harness)
            for linux in (1, 0):
                binary = root / ("frame_setup_" + str(linux))
                subprocess.run(["c++", "-std=c++17", "-DIS_LINUX=" + str(linux),
                                str(cpp), "-o", str(binary)], check=True)
                result = subprocess.run([str(binary)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0,
                    "Content backdrop contract failed (Linux=" + str(linux) + "): " + result.stderr)


if __name__ == "__main__":
    unittest.main()

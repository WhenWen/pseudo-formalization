"""Return a fully self-contained MathJax <script> block (config + the entire
SVG build inlined) so the report HTML needs NO network at all. SVG output
embeds glyph paths, so no web-font fetches; enableMenu:false avoids the
speech-rule-engine lazy-load. Call mathjax_head() and inject it into the page
AFTER .format() (the bundle contains many { } that would break str.format)."""

from pathlib import Path

_JS_PATH = Path(__file__).resolve().parent / "assets" / "tex-svg.js"

# raw string: \\( etc. become the two-char JS string '\(' as MathJax expects
_CONFIG = r"""<script>
window.MathJax = {
  tex: { inlineMath: [['$','$'],['\\(','\\)']], displayMath: [['$$','$$'],['\\[','\\]']] },
  svg: { fontCache: 'local' },
  options: { enableMenu: false, skipHtmlTags: ['script','noscript','style','textarea','pre','code'] }
};
</script>"""


def mathjax_head() -> str:
    js = _JS_PATH.read_text()
    # guard against an accidental </script> terminating the inline block
    js = js.replace("</script", "<\\/script")
    return _CONFIG + "\n<script>\n" + js + "\n</script>"

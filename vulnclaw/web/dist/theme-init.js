(function () {
  try {
    var raw = window.localStorage.getItem("vulnclaw.ui.preferences");
    var pref = raw ? JSON.parse(raw).theme : "auto";
    if (pref !== "light" && pref !== "dark") {
      pref = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.dataset.theme = pref;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", pref === "dark" ? "#0b1220" : "#f4f8fe");
  } catch (error) {
    /* 存储损坏时按浅色渲染，React 侧会写回默认值 */
  }
})();

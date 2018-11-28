// Chrome bug: https://bugs.chromium.org/p/chromium/issues/detail?id=897752

(function() {
    var isChrome = !!window.chrome && !!window.chrome.webstore;
    if (!isChrome) return;

    // check Chrome version
    var chromeVersionRe = /Chrome\/(\d+)\./;
    var m = window.navigator.userAgent.match(chromeVersionRe);
    if (!m) return;

    var chromeVersion = parseInt(m[1]);
    if (chromeVersion < 70) return; // bug appears in Chrome v70.*

    // highlight the selection with red-colored text
    var cssRule = 'svg tspan::selection {fill: red; background: none;}';

    var style = window.document.createElement('style');
    window.document.head.appendChild(style);

    style.sheet.insertRule(cssRule, 0);
})();

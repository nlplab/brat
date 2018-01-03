// External libraries
require('./client/lib/jquery.svg.min.js');
require('./client/lib/jquery.svgdom.min.js');

window.WebFont = require('./client/lib/webfont.js').WebFont;

// brat modules
window.Configuration = require('./client/src/configuration.js');
window.Util = require('./client/src/util.js');
window.Ajax = require('./client/src/ajax.js');
window.AnnotationLog = require('./client/src/annotation_log.js');
window.AnnotatorUI = require('./client/src/annotator_ui.js');
window.Dispatcher = require('./client/src/dispatcher.js');
window.OfflineAjax = require('./client/src/offline_ajax.js');
window.Spinner = require('./client/src/spinner.js');
window.Visualizer = require('./client/src/visualizer.js');
window.VisualizerUI = require('./client/src/visualizer_ui.js');

url_monitor = require('./client/src/url_monitor.js');
window.URLMonitor = url_monitor.URLMonitor;
window.URLHash = url_monitor.URLHash;

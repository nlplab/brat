var URLMonitor = (function($, window, undefined) {
    var URLMonitor = function(dispatcher) {
      var urlMonitor = this;

      var toRender = false;

      urlMonitor.args = {};
      urlMonitor.doc = null;
      urlMonitor.dir = null;

      var updateURL = function(dirChanging) {
        var uri = urlMonitor.dir + '/' + urlMonitor.doc;
        // TODO only allowed args?
        var args = $.param(urlMonitor.args);
        if (args.length) args = '?' + args;
        uri += args;
        if (uri.length) uri = '#' + uri;
        window.location.hash = uri;
        dispatcher.post('current', [urlMonitor.dir, urlMonitor.doc, urlMonitor.args]);
      };

      var setArguments = function(args, dirChanging) {
        var oldArgs = urlMonitor.args;
        urlMonitor.args = args;
        var oldArgStr = $.param(oldArgs);
        var argStr = $.param(args);
        if (oldArgStr !== argStr) {
          dispatcher.post('argsChanged', [args, oldArgs]);
        }
        updateURL();
      };

      var setDocument = function(doc, args) {
        var oldDoc = urlMonitor.doc;
        urlMonitor.doc = doc;
        if (oldDoc !== doc) {
          dispatcher.post('docChanged', [doc, oldDoc]);
        }
        setArguments(args, true);
      };

      var setDirectory = function(dir, doc, args) {
        var oldDir = urlMonitor.dir;
        urlMonitor.dir = dir;
        if (oldDir !== dir) {
          dispatcher.post('ajax', [{
              action: 'ls',
              directory: dir
            }, 'dirLoaded']);
          dispatcher.post('dirChanged', [dir, oldDir]);
        }
        setDocument(doc, args);
      }

      var updateState = function(evt) {
        var hash = window.location.hash;
        if (hash.length) {
          hash = hash.substr(1);
        }
        var oldDir = urlMonitor.dir;

        var pathAndArgs = hash.split('?');
        var path = pathAndArgs[0] || '';
        var argsStr = pathAndArgs[1] || '';
        var dir;
        var slashPos = path.lastIndexOf('/');
        if (slashPos === -1) {
          dir = '';
        } else {
          dir = path.substr(0, slashPos);
        }
        var doc = path.substr(slashPos + 1);
        var args = $.deparam(argsStr);
        setDirectory(dir, doc, args);
      };

      var forceUpdate = function() {
        $(window).trigger('hashchange');
      };

      var init = function() {
        $(window).bind('hashchange', updateState);
        forceUpdate();
      }

      dispatcher.
          on('forceUpdate', forceUpdate).
          on('setArguments', setArguments).
          on('setDocument', setDocument).
          on('setDirectory', setDirectory).
          on('init', init);

      return urlMonitor;
    };

    return URLMonitor;
})(jQuery, window);

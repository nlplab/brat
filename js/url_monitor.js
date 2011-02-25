var URLMonitor = (function($, window, undefined) {
    var PULSE = 100; // ms

    var URLMonitor = function(dispatcher) {
      var urlMonitor = this;

      var updateForced = false;
      urlMonitor.args = {};
      urlMonitor.doc = '';
      urlMonitor.dir = '';

      var forceUpdate = function() {
        updateForced = true;
      };

      var engage = function() {
        var uri = urlMonitor.dir + '/' + urlMonitor.doc;
        // TODO only allowed args?
        var args = $.param(urlMonitor.args);
        if (args.length) args = '?' + args;
        uri += args;
        if (uri.length) uri = '#' + uri;
        window.location.hash = uri;
      };

      var setArguments = function(args) {
        var oldArgs = urlMonitor.args;
        urlMonitor.args = args;
        var oldArgStr = $.param(oldArgs);
        var argStr = $.param(args);
        if (oldArgStr !== argStr) {
          dispatcher.post("args_changed", args, oldArgs);
        }
        forceUpdate();
        engage();
      };

      var setDocument = function(doc, args) {
        var oldDoc = urlMonitor.doc;
        urlMonitor.doc = doc;
        if (oldDoc !== doc) {
          dispatcher.post("doc_changed", doc, oldDoc);
        }
        setArguments(args);
      };

      var setDirectory = function(dir, doc, args) {
        var oldDir = urlMonitor.dir;
        urlMonitor.dir = dir;
        if (oldDir !== dir) {
          dispatcher.post("dir_changed", dir, oldDir);
        }
        setDocument(doc, args);
      }

      var oldHash = '';

      var pulse = function() {
        var newHash = window.location.hash;
        
        if (oldHash === newHash && !updateForced) {
          // old news; do nothing
          return;
        }
        var oldDir = urlMonitor.dir;
        oldHash = newHash;

        if (newHash.length) {
          // kill # sign
          newHash = newHash.substr(1);
        }
        var pathAndArgs = newHash.split('?');
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
        var args = {};
        if (argsStr.length) {
          $.each(argsStr.split('&'), function(argNo, arg) {
              var keyAndValue = arg.split('=');
              args[decodeURI(keyAndValue[0])] = decodeURI(keyAndValue[1]);
          });
        }
        setDirectory(dir, doc, args);
      };

      setInterval(pulse, PULSE);

      dispatcher.
          on("forceUpdate", forceUpdate).
          on("setArguments", setArguments).
          on("setDocument", setDocument).
          on("setDirectory", setDirectory);

      return urlMonitor;
    };

    return URLMonitor;
})(jQuery, window);

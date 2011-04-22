var URLMonitor = (function($, window, undefined) {
    var URLMonitor = function(dispatcher) {
      var that = this;

      var reloadData = true;

      that.args = {};
      that.doc = null;
      that.dir = null;

      var updateURL = function() {
        var uri = that.dir + that.doc;
        // TODO only allowed args?
        var args = $.param(that.args);
        if (args.length) args = '?' + args;
        uri += args;
        if (uri.length) uri = '#' + uri;
        window.location.hash = uri;
        // if a form is open, it shouldn't be now.
        dispatcher.post('hideForm');
      };

      var setArguments = function(args, dirChanging) {
        var oldArgs = that.args || {};
        that.args = args || {};
        var oldArgStr = $.param(oldArgs);
        var argStr = $.param(that.args);
        if (oldArgStr !== argStr) {
          dispatcher.post('argsChanged', [args, oldArgs]);
        }
        updateURL();
      };

      var setDocument = function(doc, args) {
        var oldDoc = that.doc;
        that.doc = doc;
        if (oldDoc !== doc) {
          dispatcher.post('docChanged', [doc, oldDoc]);
        }
        setArguments(args || {}, true);
      };

      var setDirectory = function(dir, doc, args) {
        var oldDir = that.dir;
        that.dir = dir;
        if (oldDir !== dir) {
          dispatcher.post('ajax', [{
              action: 'getDirectoryInformation',
              directory: dir
            }, 'dirLoaded', {
              directory: dir
            }]);
          dispatcher.post('dirChanged', [dir, oldDir]);
        }
        setDocument(doc || '', args);
      }

      var updateState = function(evt) {
        var hash = window.location.hash;
        if (hash.length) {
          hash = hash.substr(1);
        }
        var oldDir = that.dir;

        var pathAndArgs = hash.split('?');
        var path = pathAndArgs[0] || '';
        var argsStr = pathAndArgs[1] || '';
        var dir;
        var slashPos = path.lastIndexOf('/');
        if (slashPos === -1) {
          dir = '/';
        } else {
          dir = path.substr(0, slashPos + 1);
          if (dir[dir.length - 1] !== '/') {
            dir += '/';
          }
          if (dir[0] !== '/') {
            dir = '/' + dir;
          }
        }
        var doc = path.substr(slashPos + 1);
        var args = $.deparam(argsStr);

        setDirectory(dir, doc, args);
        dispatcher.post('current', [that.dir, that.doc, that.args, reloadData]);
        reloadData = true;
      };

      var forceUpdate = function() {
        $(window).trigger('hashchange');
      };

      var preventReloadByURL = function() {
        reloadData = false;
      }

      var init = function() {
        $(window).bind('hashchange', updateState);
        forceUpdate();
      }

      dispatcher.
          on('forceUpdate', forceUpdate).
          on('setArguments', setArguments).
          on('setDocument', setDocument).
          on('setDirectory', setDirectory).
          on('preventReloadByURL', preventReloadByURL).
          on('init', init);
    };

    return URLMonitor;
})(jQuery, window);

// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var URLMonitor = (function($, window, undefined) {
    var URLMonitor = function(dispatcher) {
      var that = this;

      var reloadData = true;

      that.args = null;
      that.doc = null;
      that.coll = null;

      var updateURL = function() {
        var uri = that.coll + that.doc;
        // TODO only allowed args?
        var args = that.args === null ? '' : $.param(that.args);
        if (args.length) args = '?' + args;
        uri += args;
        if (uri.length) uri = '#' + uri;
        window.location.hash = uri;
        // if a form is open, it shouldn't be now.
        dispatcher.post('hideForm');
      };

      var setArguments = function(args, collChanging) {
        var oldArgs = that.args === null ? '' : that.args;
        that.args = args === null ? '' : args;
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
        setArguments(args || '', true);
      };

      var setCollection = function(coll, doc, args) {
        var oldColl = that.coll;
        that.coll = coll;
        if (oldColl !== coll) {
          dispatcher.post('ajax', [{
              action: 'getCollectionInformation',
              collection: coll
            }, 'collectionLoaded', {
              collection: coll
            }]);
          dispatcher.post('collectionChanged', [coll, oldColl]);
        }
        setDocument(doc || '', args);
      }

      var updateState = function(evt) {
        var hash = window.location.hash;
        if (hash.length) {
          hash = hash.substr(1);
        }
        var oldColl = that.coll;

        var pathAndArgs = hash.split('?');
        var path = pathAndArgs[0] || '';
        var argsStr = pathAndArgs[1] || '';
        var coll;
        var slashPos = path.lastIndexOf('/');
        if (slashPos === -1) {
          coll = '/';
        } else {
          coll = path.substr(0, slashPos + 1);
          if (coll[coll.length - 1] !== '/') {
            coll += '/';
          }
          if (coll[0] !== '/') {
            coll = '/' + coll;
          }
        }
        var doc = path.substr(slashPos + 1);
        var args = $.deparam(argsStr);
        // deparam() gives {} for any empty, using null internally for
        // ease of comparison. (BTW what kind of language doesn't
        // provide an inbuilt mechanism for checking for an empty
        // primitive??)
        if ($.isEmptyObject(args)) {
          args = null;
        }

        setCollection(coll, doc, args);
        dispatcher.post('current', [that.coll, that.doc, that.args, reloadData]);
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
          on('setCollection', setCollection).
          on('preventReloadByURL', preventReloadByURL).
          on('init', init);
    };

    return URLMonitor;
})(jQuery, window);

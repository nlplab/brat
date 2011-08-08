// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var URLMonitor = (function($, window, undefined) {
    var URLMonitor = function(dispatcher) {
      var that = this;

      var reloadData = true;

      that.url_hash = new URLHash();

      var updateURL = function() {
        window.location.hash = that.url_hash.getHash();
        dispatcher.post('hideForm');
      };

      var setArguments = function(args) {
        var oldArgs = that.url_hash.arguments;
        if (!Util.isEqual(oldArgs, args)) {
          that.url_hash.setArguments(args);
          dispatcher.post('argsChanged', [args, oldArgs]);
        }
        updateURL();
      };

      var setDocument = function(doc, args) {
        var oldDoc = that.url_hash.document;
        if (oldDoc !== doc) {
          that.url_hash.setDocument(doc);
          dispatcher.post('docChanged', [doc, oldDoc]);
        }

        setArguments(args || null);
      };

      var setCollection = function(coll, doc, args) {
        var oldColl = that.url_hash.collection;
        if (oldColl !== coll) {
          that.url_hash.setCollection(coll);

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

      var updateState = function() {
        var new_url_hash = URLHash.parse(window.location.hash);
        setCollection(new_url_hash.collection, new_url_hash.document,
            new_url_hash.arguments)
       
        dispatcher.post('current', [that.url_hash.collection,
            that.url_hash.document, that.url_hash.arguments, reloadData]);
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

var URLHash = (function($, window, undefined) {
    var URLHash = function(collection, _document, _arguments) {
      var that = this;
      that.collection = collection;
      that.document = _document || '';
      that.arguments = _arguments || {};
    }

    URLHash.prototype = {
      setArgument: function(argument, value) {
        if (!this.arguments) {
          this.arguments = {};
        }
        this.arguments[argument] = value;
      },

      setArguments: function(_arguments) {
        this.arguments = _arguments || {};
      },

      setDocument: function(_document) {
        this.document = _document;
      },

      setCollection: function(collection) {
        this.collection = collection;
      },

      getHash: function() {
        var url_hash = this.collection + this.document;
        var url_args = param(this.arguments);

        if (url_args.length) {
          url_hash += '?' + url_args;
        }

        if (url_hash.length) {
          url_hash = '#' + url_hash;
        }

        return url_hash;
      },
    };

    var equalsRE = /^([^=]+)=(.*)$/;

    var deparam = function(str) {
      var args = str.split('&');
      var len = args.length;
      if (!len) return null;
      var result = {};
      for (var i = 0; i < len; i++) {
        var parts = args[i].match(equalsRE);
        if (parts.length != 3) break;
        var val = [];
        var arr = parts[2].split(',');
        var sublen = arr.length;
        for (var j = 0; j < sublen; j++) {
          val.push(arr[j].split('-'));
        }
        result[parts[1]] = val;
      }
      return result;
    };

    var param = function(args) {
      if (!args) return '';
      var vals = [];
      for (var key in args) {
        if (args.hasOwnProperty(key)) {
          var val = args[key];
          var len = val.length;
          var arr = [];
          for (var i = 0; i < len; i++) {
            arr.push(val[i].join('-'));
          }
          vals.push(key + '=' + arr.join(','));
        }
      }
      return vals.join('&');
    };

    // TODO: Document and conform variables to the rest of the object
    URLHash.parse = function(hash) {
      if (hash.length) {
        // Remove the leading hash (#)
        hash = hash.substr(1);
      }

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
      var args = deparam(argsStr);
      return new URLHash(coll, doc, args);
    };

    return URLHash;
})(jQuery, window)

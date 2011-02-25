var URLMonitor = (function($, window, undefined) {
    var PULSE = 100; // ms

    var URLMonitor = function(dispatcher) {
      var updateForced = false;

      var forceUpdate = function() {
        updateForced = true;
      };

      var engage = function() {
        var temp = '#' + this.dir + '/' + this.doc;
        // TODO prettify (conditional "?", only allowed args)
        temp += '?' + $.param(this.args);
        window.location.hash = temp;
      };

      var setArguments = function(args) {
        this.args = args;
        forceUpdate();
        engage();
      };

      var setDocument = function(doc, args) {
        this.doc = doc;
        setArguments(args);
      };

      var setDirectory = function(dir, doc, args) {
        this.dir = dir;
        setDocument(doc, args);
      }

      var oldHash = {};

      var pulse = function() {
        var newHash = window.location.hash;
        
        if (oldHash === newHash && !updateForced) {
          // old news; do nothing
          return;
        }
        var oldDir = this.dir;
        oldHash = newHash;

        if (newHash.length) {
          // kill # sign
          newHash = newHash.substr(1);
        }
        var pathAndArgs = newHash.split('?');
        var path = pathAndArgs[0] || '';
        var args = pathAndArgs[1] || '';
        var slashPos = path.lastIndexOf('/');
        if (slashPos === -1) {
          this.dir = '';
        } else {
          this.dir = path.substr(0, slashPos);
        }
        this.doc = path.substr(slashPos + 1);
        this.args = {};
        if (args.length) {
          $.each(args.split('&'), function(argNo, arg) {
              var keyAndValue = arg.split('=');
              this.args[decodeURI(keyAndValue[0])] = decodeURI(keyAndValue[1]);
          });
        }
        engage();


        if (oldDir !== this.dir) {
          dispatcher.post(0, "chdir", this.dir);
        }
      };

      setInterval(pulse, PULSE);

      dispatcher.
          on("forceUpdate", forceUpdate).
          on("setArguments", setArguments).
          on("setDocument", setDocument).
          on("setDirectory", setDirectory);
    };

    return URLMonitor;
})(jQuery, window);

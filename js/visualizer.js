var Visualizer = (function($, window, undefined) {
    var Visualizer = function(dispatcher, svg) {
      var visualizer = this;

      var data = null;

      var rerender = function() {
        // render current data
      };

      var render = function(_data) {
        data = _data;
        rerender();
      };

      dispatcher.
          on("render", render);
          on("rerender", rerender);
    };

    return Visualizer;
})(jQuery, window);
